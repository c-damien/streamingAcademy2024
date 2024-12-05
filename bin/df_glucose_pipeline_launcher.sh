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

#Update in the following statement elememnts in curly brackets after saving go to your console and launch bash df_glucose_launcher.sh
pip3 install -r requirements.txt

python3 -m df_glucose_pipeline \
--project_id="{project_id}" \ 
--region="us-central1" \
--subnetwork_name="https://www.googleapis.com/compute/v1/projects/{project_id}/regions/us_central1/subnetworks/s-academy-us" \
--staging_dir="gs://streamingacademy2024_{project.number}/dataflow/staging" \
--temp_dir="gs://streamingacademy2024_{project.number}/dataflow/temp" \
--gemini_model="gemini-1.5-flash-002" \
--input_subscription="projects/{project_id}/subscriptions/glucose_monitoring-sub" \
--output_step_topic="projects/{project_id}/topics/output_count_step" \
--output_glucose_topic="projects/{project_id}/topics/output_avg_glucose_level" \
--output_table="gs://{project_id}/output/my_table"


