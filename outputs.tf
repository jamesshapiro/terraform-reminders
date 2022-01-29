# Output value definitions

output "lambda_bucket_name" {
  description = "Name of the S3 bucket used to store function code."

  value = aws_s3_bucket.lambda_bucket.id
}

output "create_reminder_function_name" {
  description = "Name of the Lambda function."
  value = aws_lambda_function.create_reminder.function_name
}

output "url" {
  description = "API Gateway endpoint."
  value = "${aws_api_gateway_stage.prod.invoke_url}${aws_api_gateway_resource.resource.path}"
}