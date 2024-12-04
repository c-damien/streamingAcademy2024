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
#Parameters:
#$1 projectid
#$2 region
#$3 bucketname
#$4 folder
#$5 nb customers

#Update in the following statement elememnts in curly brackets and copy and paste it in your console to execute
#bash msg_generator.sh {project_id} streamingacademy2024 data glucose_monitoring 32

#install necessary libs
pip3 install -r requirements.txt

#set default project
gcloud config set project $1

#launch generator
python3 -m msg_generator \
--project_id $1 \
--bucket_name $2 \
--folder_name $3 \
--topic_id $4 \
--threads_count $5 \
