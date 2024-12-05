# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     https://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
####################################################################################


####################################################################################
# Main script used to provision the different asset used in the following demo:
#               Streaming Academy 2024 - Troubleshooting
#
# Author: Damien Contreras cdamien@google.com
####################################################################################

import apache_beam as beam
from apache_beam import pvalue, window, WindowInto
from apache_beam.transforms.window import TimestampedValue
from apache_beam.transforms.trigger import AccumulationMode, AfterCount, AfterAll, AfterWatermark, AfterAny, Repeatedly, AfterEach, AfterProcessingTime

from apache_beam.utils.timestamp import MAX_TIMESTAMP
from apache_beam.utils.timestamp import Timestamp
from apache_beam.utils.timestamp import Duration

from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.io import fileio
from apache_beam.io.gcp.pubsub import ReadFromPubSub

from apache_beam.metrics import Metrics

#dataflow runner
from apache_beam.runners import DataflowRunner

from datetime import datetime
import traceback, sys
import time
import logging
import json
import gzip
import base64
import numpy as np
import pyarrow as pyarrow
from io import StringIO
import argparse


from google.cloud import storage
import vertexai
from vertexai.generative_models import (
    GenerationConfig,
    GenerativeModel,
    HarmBlockThreshold,
    HarmCategory,
    Part,
    SafetySetting
)

##INPUT_TOPIC = "projects/streamingacademy2024/topics/glucose_monitoring"
#INPUT_SUBSCRIPTION = "projects/streamingacademy2024/subscriptions/glucose_monitoring-sub"
#OUTPUT_STEP_TOPIC = "projects/streamingacademy2024/topics/output_count_step"
#OUTPUT_GLUCOSE_TOPIC = "projects/streamingacademy2024/topics/output_avg_glucose_level"

#PROJECT_ID = "streamingacademy2024"
#REGION = "us-central1"
#MODEL =  "gemini-1.5-flash-002"
##network: streaming-academy-vpc
##subnet: s-academy-us
#SUBNETWORK_NAME = "https://www.googleapis.com/compute/v1/projects/"+PROJECT_ID+"/regions/"+REGION+"/subnetworks/us-resources"
#OUTPUT_TABLE = "gs://streamingacademy2024/output/my_table"
#STAGING = "gs://streamingacademy2024/dataflow/staging"
#TEMP = "gs://streamingacademy2024/dataflow/temp"

logger= logging.getLogger('log')
logger.setLevel(logging.INFO)
####################################################################################


class Load_data_from_gcs(beam.DoFn):
    def process(self, element):
        """
        Reads a gunzip file from Google Cloud Storage (GCS) and parses each line as a JSON record.
        "streamingacademy2024", "data/"
      Args:
        bucket_name: The name of the GCS bucket.
        file_name: The name of the gunzip file in the bucket.
      Returns:
         JSON records.
        """
        
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(element['bucket_name'])
        blob = bucket.blob(element['folder_name']+"/"+element['file_name'])
        content = blob.download_as_bytes()
        #print("--reading file:"+element['file_name'])
        with blob.open("rb") as f:
             with gzip.GzipFile(fileobj=f) as gz:
                for line in gz:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON: {e}")


def sum_elements(values):
    total = 0
    for number in values: #solution use sum in python
        total += number
    return total

class CallVertexAIGeminiModel(beam.DoFn):
    m = None
    def setup(self):
        vertexai.init(project=PROJECT_ID, location=REGION)

    def process(self, elements):
        m = GenerativeModel(
            "gemini-1.5-flash-002",
            system_instruction=[
            "You are a helpful medical advisor teaching to students",
            "Your mission is to make lifestyle recommendation based on glucose level and steps count aggregated for the past 10 minutes",
            ]
        )
    
        # Set model parameters
        generation_config = GenerationConfig(
            temperature=0.4,
            top_p=1.0,
            top_k=10,
            candidate_count=1,
            max_output_tokens=8192,
        )
            
        # Set safety settings
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }
        
        avg_glucose = 0
        if len(elements[1]['glucose']) > 0:
            avg_glucose = sum(elements[1]['glucose']) / len(elements[1]['glucose'])
        
        total_steps = 0
        if len(elements[1]['steps'])>0:
            total_steps = sum(elements[1]['steps']) 
        
        #prompt
        prompt = """
        for study purpose, you are showing students how to diagnose potential illness and make lifestyle and habits recommendation , 
        based on the following data from a patient, glucose level:"""+str(avg_glucose)+""" mg/dL, steps counted for the last 10 mins:"""+str(total_steps)+""" steps, 
        Give a textual recommendations given the 2 indicators ?"""

        contents = [prompt]
        response = m.generate_content(contents, generation_config=generation_config, safety_settings=safety_settings,)
        
        recommendation = ""
        try:
            recommendation = response.text
        except Exception as e:
            # Handle the ValueError
            print(f"ValueError occurred: {e}")
            
            
        yield {"account":elements[0], "total_steps":total_steps, "avg_glucose":avg_glucose, "recommendation":recommendation }   

####################################################################################
def run():
    parser = argparse.ArgumentParser(description="Expect 7 parameters")
    parser.add_argument("--project_id", type=str, help="GCP project")
    parser.add_argument("--region", type=str, help="region")
    parser.add_argument("--subnetwork_name", type=str, help="")
    parser.add_argument("--staging_dir", type=str, help="")
    parser.add_argument("--temp_dir", type=str, help="")
    parser.add_argument("--gemini_model", help="gemini model")
    parser.add_argument("--input_subscription", help="pub/sub topic")
    parser.add_argument("--output_step_topic", help="pub/sub sub")
    parser.add_argument("--output_glucose_topic", help="pub/sub topic")
    parser.add_argument("--output_table", help="pub/sub topic")

    args = parser.parse_args()

    global PROJECT_ID, REGION, SUBNETWORK_NAME, STAGING, TEMP, MODEL, INPUT_SUBSCRIPTION, OUTPUT_STEP_TOPIC, OUTPUT_GLUCOSE_TOPIC, OUTPUT_TABLE
    PROJECT_ID = args.project_id
    REGION = args.region
    SUBNETWORK_NAME=args.subnetwork_name
    STAGING= args.staging_dir
    TEMP= args.temp_dir
    MODEL=args.gemini_model
    INPUT_SUBSCRIPTION=args.input_subscription
    OUTPUT_STEP_TOPIC=args.output_step_topic
    OUTPUT_GLUCOSE_TOPIC=args.output_glucose_topic
    OUTPUT_TABLE=args.output_table

    dataflow_options = PipelineOptions(
       flags=[],
       streaming=True,
       project=PROJECT_ID,
       runner='DataflowRunner',
       save_main_session=True,
       requirements_file="requirements.txt",
       region=REGION,
       max_num_workers=4,
       #machine_type="n1-highmem-4", #solution switch to n1-
       subnetwork=SUBNETWORK_NAME,
       dataflow_service_options=["enable_google_cloud_profiler"],
       experiments=["enable_data_sampling"],
       staging_location=STAGING,
       temp_location=TEMP
    )

    with beam.Pipeline(DataflowRunner(), options=dataflow_options) as pipeline: #DataflowRunner #InteractiveRunner(),
     
        stage1 = (
            pipeline
            | "Read msg s1"   >> beam.io.ReadFromPubSub(subscription=INPUT_SUBSCRIPTION)
            | 'Parse Json s1' >> beam.Map(json.loads)
            | 'Adding ts s1'  >> beam.Map(lambda x: beam.window.TimestampedValue(x, datetime.fromisoformat(x['event_time']).timestamp()))
            | 'Read file s1'    >>  beam.ParDo(Load_data_from_gcs())
            | 'Adding elt ts s1' >> beam.Map(lambda x: beam.window.TimestampedValue(x, x['time'])) # solution
            | "Reshuffle s1" >> beam.Reshuffle(num_buckets=1000)
           )
            
           
            #| "Add id" >> beam.WithKeys(lambda x:  datetime.fromisoformat(x['event_time']))
            # beam.window.TimestampedValue
         #| 'adding key' >> beam.Map(lambda x: (str(x['latitude'])[:6] + "_" + str(x['longitude'])[:8], x))
            #| 'distinct s1'  >>  beam.Distinct()
            #| "Reshuffle s1" >> beam.Reshuffle(num_buckets=1000) #solution

        
        #steps count per 5 mins
        stage2 = (
            stage1
            | 'Window5min' >> beam.WindowInto(window.FixedWindows(300)) #5 mins
            | 'k,v conv s2' >> beam.Map(lambda x:(x['account'], x['steps_count'])) # solution to key
            | 'Aggr s2' >> beam.CombinePerKey(sum_elements) #solution using sum directly
            | 'Window s2' >> beam.WindowInto(beam.window.FixedWindows(300), allowed_lateness=Duration(seconds=300))
        )
        
        #average glucose
        stage3 = (
            stage1
            | 'slidingWindow' >> beam.WindowInto(beam.window.SlidingWindows(size=900, period=300)) # 15 mins
            | 'k,v conv s3' >> beam.Map(lambda x:(x['account'], x['glucose_level'])) # solution to key
            | 'Aggr s3' >> beam.CombinePerKey(beam.combiners.MeanCombineFn()) #solution
            | 'Window s3' >> beam.WindowInto(beam.window.FixedWindows(300), allowed_lateness=Duration(seconds=300))
        )
        
        #steps count per 10 mins
        stage4 = (
            stage1
            | 'Window10min' >> beam.WindowInto(window.FixedWindows(600)) #5 mins
            | 'k,v conv s4' >> beam.Map(lambda x:(x['account'], x['steps_count']))
            | 'Aggr s4' >> beam.CombinePerKey(sum_elements) #solution using sum directly
            | 'prepare to send' >> beam.Map(lambda x:json.dumps({"account":x[0],"total_steps":x[1]}))
            | 'to json s4' >> beam.Map(lambda x:json.dumps(x).encode("utf-8"))
            | 'write to pub/sub 1' >> beam.io.WriteToPubSub(topic=OUTPUT_STEP_TOPIC)
        )
                                                                      
        #Combine data and call gemini
        stage5 = (({'steps': stage2, 'glucose': stage3})
            |'Merge stage 2 & 3' >> beam.CoGroupByKey()
            |'Call Gemini' >> beam.ParDo(CallVertexAIGeminiModel())
        )
        
        #save raw data to parquet
        schema = pyarrow.schema([('account', pyarrow.string()), 
                                  ('total_steps', pyarrow.int64()), 
                                  ('avg_glucose', pyarrow.float64()),
                                  ('recommendation', pyarrow.string())])
        
        #stage6 =(stage5
        #        | 'write all to parquet' >> beam.io.WriteToParquet(  
        #        file_path_prefix= OUTPUT_TABLE, 
        #        schema=schema,
        #        num_shards=1)
        #)
        
        #save aggregation to pub/sub
        stage7 = (stage5
                  | 'to json all' >> beam.Map(lambda x:json.dumps(x).encode("utf-8"))
                  | 'write to pub/sub 2' >> beam.io.WriteToPubSub(topic=OUTPUT_GLUCOSE_TOPIC)
                 )


if __name__ == '__main__':
  run()





