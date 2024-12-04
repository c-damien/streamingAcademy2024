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

import random
from datetime import datetime
from datetime import datetime, timedelta
import io
import json
import numpy as np
from google.cloud import storage
import os
import argparse

#multithreading
import time
import threading
import logging
import random
import re
from google.cloud import storage
from multiprocessing import Process, Pipe

#pub/sub
from google.api_core.exceptions import NotFound
from google.cloud.pubsub import PublisherClient

logger = logging.getLogger('log')
logger.setLevel(logging.INFO)

minutes_in_15_days = 15 * 24 * 60


def list_files_in_subfolder(bucket_name, subfolder_path):

          storage_client = storage.Client()
          bucket = storage_client.bucket(bucket_name)

          files = list(bucket.list_blobs(prefix=subfolder_path))
          file_names = [re.sub(r"^data/", "", file.name) for file in files if not file.name.endswith('/')]

          return file_names

class generateMessages (Process):
     

    def __init__(self, threadID, file_list):
        super().__init__()
        self.threadID = threadID
        self.publisher_client = PublisherClient()
        self.topic_path =  self.publisher_client.topic_path(PROJECT_ID, TOPIC_ID)
        available_files = file_list
        pattern = r"records_"+str(threadID)+"_\d+\_\d+\.gz"  # The regex pattern
        self.matching_items = [file for file in available_files if re.match(pattern, file)]

    def run(self):
        
        for i in range(0, 120): #run for 2 hours
            for f in self.matching_items:
                account_offset = 0
                pattern = r"records_\d+_(\d+)_\d+\.gz"  # Regex with capturing group
                match = re.match(pattern, f)
                if match:
                    account_offset = match.group(1)
                    account_id = str(self.threadID) + str(account_offset)
                    self.sendToPubSub(account_id, f)
                    time.sleep(60)

        #total_samples = int(END_TIME/60 - START_TIME/60)
        #for account_offset in range(0, 1): # 200,000 customer
        #    account_id = str(self.threadID) + str(account_offset)
        #    for i in range(0, 10): #total_samples):
        #        file_name = 'records_'+ str(self.threadID) + "_" + str(account_offset) + "_"+ str(START_TIME + minutes_in_15_days*60 + 60*i ) +'.gz'
        #        self.sendToPubSub(account_id, file_name)
        #        time.sleep(60)

    def sendToPubSub(self, account_id, file_name):
        try:
            record = {
                "account_id":account_id,
                "event_time":datetime.now().isoformat(),
                "bucket_name": BUCKET_NAME,
                "folder_name": FOLDER_NAME,
                "file_name":file_name
            }
            data_str = json.dumps(record)
            data = data_str.encode("utf-8") 
            print(f"Publishing: {file_name}")
            future = self.publisher_client.publish(self.topic_path, data)
            print(f"Published message ID: {future.result()}")
        except NotFound:
            print(f"{topic_id} not found.")

# multithreading
def main():
    parser = argparse.ArgumentParser(description="Expect 7 parameters")
    parser.add_argument("--project_id", type=str, help="GCP project")
    parser.add_argument("--bucket_name", type=str, help="GCS bucket")
    parser.add_argument("--folder_name", type=str, help="folder in GCS with data")
    parser.add_argument("--topic_id", type=str, help="topic where to pish the data")
    parser.add_argument("--start_time", type=int, help="unix time stamp")
    parser.add_argument("--end_time", type=int, help="unix time stamp")
    parser.add_argument("--threads_count", type=int, help="nb threads")

    args = parser.parse_args()

    global PROJECT_ID, BUCKET_NAME, FOLDER_NAME, TOPIC_ID, THREADS_COUNT #,START_TIME, END_TIME,
    PROJECT_ID = args.project_id
    BUCKET_NAME = args.bucket_name
    FOLDER_NAME = args.folder_name
    TOPIC_ID = args.topic_id
    #START_TIME = args.start_time
    #END_TIME = args.end_time
    THREADS_COUNT = args.threads_count

    exitFlag = 0
    threadLock = threading.Lock()
    threads = []

    i = 0
    file_list = list_files_in_subfolder(BUCKET_NAME, FOLDER_NAME)
    try:
        for i in range(0, THREADS_COUNT, file_list):
            p = generateMessages(i)
            p.start()
            threads.append(p)
            i+=1
        for t in threads:
              t.join()

    except Exception as e:
          logger.error("Error: unable to start thread:" + e)

if __name__ == '__main__':
    main()