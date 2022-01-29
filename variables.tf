# Input variable definitions

variable "aws_region" {
  description = "AWS region for all resources."
  type    = string
}

variable "account_id" {
  description = "AWS region for all resources."
  type    = string
}

variable "notification_email" {
  description = "Email target for reminders."
  type    = string
}

# For US numbers should be of the form +12223334444
variable "notification_phone_number" {
  description = "Phone number for text reminders."
  type    = string
}