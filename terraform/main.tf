####################################################################################
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

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google-beta"
      version = ">= 4.52, < 6"
    }
  }
}

#get default parameters:
data "google_client_config" "default" {
}

# get Google Cloud project
data "google_project" "project" {}

variable "region" {
  type = string
  default = "us-central1"
}

###activate APIs
resource "google_project_service" "google-cloud-apis" {
  project = data.google_project.project.project_id 
  for_each = toset([
    "cloudresourcemanager.googleapis.com",
    "aiplatform.googleapis.com",
    "servicenetworking.googleapis.com",
    "compute.googleapis.com",
    "dataflow.googleapis.com",
    "pubsub.googleapis.com",
    "storage-component.googleapis.com",
  ])
  disable_dependent_services = true
  disable_on_destroy         = true
  service                    = each.key
}

######## Create network
resource "google_compute_network" "main-vpc" {
  name                    = "streaming-academy-vpc"
  auto_create_subnetworks = false # Important: prevent auto-creation of subnets
 project                 = data.google_project.project.project_id
}

######## Create subnet
resource "google_compute_subnetwork" "main-subnet" {
  name          = "s-academy-us"
  ip_cidr_range = "10.140.0.0/20"
  region        = "${var.region}"
  network       = google_compute_network.main-vpc.name
  project       = data.google_project.project.project_id
  private_ip_google_access = true

  depends_on = [
    google_compute_network.main-vpc 
  ]
}

######## create a gce instance to get the default user
resource "google_compute_instance" "dummy" {
  name         = "dummy-instance"
  machine_type = "e2-medium"
  zone         = "us-central1-a"
  project      = data.google_project.project.project_id

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.main-subnet.name
  }
}


######## create pub/sub topics
resource "google_pubsub_topic" "input_topic" {
  name = "glucose_monitoring"
  project = data.google_project.project.project_id
}

resource "google_pubsub_topic" "output_topic_1" {
  name = "output_count_step"
  project = data.google_project.project.project_id
}

resource "google_pubsub_topic" "output_topic_2" {
  name = "output_avg_glucose_level"
  project = data.google_project.project.project_id
}

######## create subscription
resource "google_pubsub_subscription" "input_topic_sub" {
  name  = "glucose_monitoring-sub"
  topic = google_pubsub_topic.input_topic.name
  project = data.google_project.project.project_id

  depends_on = [
    google_pubsub_topic.input_topic 
  ]
}
resource "google_pubsub_subscription" "output_topic_1_sub" {
  name  = "output_count_step-sub"
  topic = google_pubsub_topic.input_topic.name
  project = data.google_project.project.project_id

  depends_on = [
    google_pubsub_topic.output_topic_1 
  ]
}

resource "google_pubsub_subscription" "output_topic_2_sub" {
  name  = "output_avg_glucose_level-sub"
  topic = google_pubsub_topic.input_topic.name
  project = data.google_project.project.project_id
  depends_on = [
    google_pubsub_topic.output_topic_2 
  ]
}

######## create gcs bucket
resource "google_storage_bucket" "sa_bucket" {
 name          = "streamingacademy2024_${data.google_project.project.number}" 
 location      = "${var.region}"
 storage_class = "STANDARD"
 force_destroy               = true
 uniform_bucket_level_access = true
}

######## Create sub folders
resource "google_storage_bucket_object" "folder_dataflow" {
  name          = "dataflow/"
  content       = "Not really a directory, but it's empty."
  bucket        = "${google_storage_bucket.sa_bucket.name}"

  depends_on = [
    google_storage_bucket.sa_bucket
  ]
}

resource "google_storage_bucket_object" "folder_output" {
  name          = "output/"
  content       = "Not really a directory, but it's empty."
  bucket        = "${google_storage_bucket.sa_bucket.name}"

  depends_on = [
    google_storage_bucket.sa_bucket
  ]
}

resource "google_storage_bucket_object" "folder_config" {
  name          = "dataflow/config/"
  content       = "Not really a directory, but it's empty."
  bucket        = "${google_storage_bucket.sa_bucket.name}"

  depends_on = [
    google_storage_bucket_object.folder_dataflow
  ]
}

resource "google_storage_bucket_object" "folder_staging" {
  name          = "dataflow/staging/"
  content       = "Not really a directory, but it's empty."
  bucket        = "${google_storage_bucket.sa_bucket.name}"
  depends_on = [
    google_storage_bucket_object.folder_dataflow
  ]
}
resource "google_storage_bucket_object" "folder_temp" {
  name          = "dataflow/temp/"
  content       = "Not really a directory, but it's empty."
  bucket        = "${google_storage_bucket.sa_bucket.name}"
  depends_on = [
    google_storage_bucket_object.folder_dataflow
  ]
}

######## Set all permission
#Vertex AI
resource "google_project_iam_binding" "vertex" {
  project = "${data.google_project.project.id}"
  role    = "roles/aiplatform.user"
  members = [
    "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com",
  ]
  depends_on = [
    google_compute_instance.dummy
  ]
}
# Dataflow
resource "google_project_iam_binding" "df_worker" {
  project = "${data.google_project.project.id}"
  role    = "roles/dataflow.worker"
  members = [
    "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com",
  ]
  depends_on = [
    google_compute_instance.dummy
  ]
}
resource "google_project_iam_binding" "df_admin" {
  project = "${data.google_project.project.id}"
  role    = "roles/dataflow.admin"
  members = [
    "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com",
  ]
  depends_on = [
    google_compute_instance.dummy
  ]
}
resource "google_project_iam_binding" "pubsub" {
  project = "${data.google_project.project.id}"
  role    = "roles/pubsub.admin"
  members = [
    "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com",
  ]
  depends_on = [
    google_compute_instance.dummy
  ]
}
resource "google_project_iam_binding" "gcs" {
  project = "${data.google_project.project.id}"
  role    = "roles/storage.admin"
  members = [
    "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com",
  ]
  depends_on = [
    google_compute_instance.dummy
  ]
}
