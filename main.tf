terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 3.48.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.2.0"
    }
  }

  required_version = "~> 1.0"
}

provider "aws" {
  region = var.aws_region
}

resource "random_pet" "lambda_bucket_name" {
  prefix = "learn-terraform-functions"
  length = 2
}

resource "aws_s3_bucket" "lambda_bucket" {
  bucket = random_pet.lambda_bucket_name.id

  acl           = "private"
  force_destroy = true
}

data "archive_file" "archive" {
  type = "zip"

  source_dir  = "${path.module}/functions"
  output_path = "${path.module}/archive.zip"
}

resource "aws_s3_bucket_object" "archive" {
  bucket = aws_s3_bucket.lambda_bucket.id

  key    = "archive.zip"
  source = data.archive_file.archive.output_path

  etag = filemd5(data.archive_file.archive.output_path)
}

resource "aws_lambda_layer_version" "ulid_layer" {
  filename   = "my-Python38-ulid.zip"
  layer_name = "ulid_layer"
  compatible_runtimes = ["python3.8"]
}

resource "aws_lambda_function" "create_reminder" {
  function_name = "terraform-create-reminder"

  s3_bucket = aws_s3_bucket.lambda_bucket.id
  s3_key    = aws_s3_bucket_object.archive.key

  runtime = "python3.8"
  handler = "create_reminder.lambda_handler"
  layers = [aws_lambda_layer_version.ulid_layer.arn]

  source_code_hash = data.archive_file.archive.output_base64sha256

  environment {
    variables = {
      REMINDERS_DDB_TABLE = aws_dynamodb_table.reminder_table.name
    }
  }

  role = aws_iam_role.lambda_exec.arn
}

resource "aws_dynamodb_table" "reminder_table" {
  name           = "TerraformReminderTable"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "PK1"
  range_key      = "SK1"

  attribute {
    name = "PK1"
    type = "S"
  }

  attribute {
    name = "SK1"
    type = "S"
  }
}

resource "aws_cloudwatch_log_group" "create_reminder_logs" {
  name = "/aws/lambda/${aws_lambda_function.create_reminder.function_name}"
  retention_in_days = 30
}

resource "aws_iam_role" "lambda_exec" {
  name = "terraform_reminders_lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Sid    = ""
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      }
    ]
  })
}

resource "aws_iam_policy" "ddb_write_permissions" {
  name        = "terraform_reminders_ddb_write_permissions"
  description = "Allow Lambda to write to DDB"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = [
        "dynamodb:BatchWrite*",
        "dynamodb:Update*",
        "dynamodb:PutItem"
      ]
      Effect = "Allow"
      Resource = aws_dynamodb_table.reminder_table.arn
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_ddb_write_policy" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.ddb_write_permissions.arn
}

resource "aws_api_gateway_rest_api" "api" {
  name          = "terraform_reminders"
}

resource "aws_api_gateway_resource" "resource" {
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "upload-reminder"
  rest_api_id = aws_api_gateway_rest_api.api.id
}

resource "aws_api_gateway_method" "method" {
  authorization    = "NONE"
  http_method      = "POST"
  api_key_required = true
  resource_id      = aws_api_gateway_resource.resource.id
  rest_api_id      = aws_api_gateway_rest_api.api.id
}

resource "aws_api_gateway_integration" "integration" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.resource.id
  http_method             = aws_api_gateway_method.method.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.create_reminder.invoke_arn
}

resource "aws_api_gateway_deployment" "deployment" {
  rest_api_id = aws_api_gateway_rest_api.api.id

  triggers = {
    redeployment = sha1(jsonencode(aws_api_gateway_rest_api.api.body))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.deployment.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
  stage_name    = "prod"
}

# Lambda
resource "aws_lambda_permission" "apigw_lambda" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.create_reminder.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn = "arn:aws:execute-api:${var.aws_region}:${var.account_id}:${aws_api_gateway_rest_api.api.id}/*/${aws_api_gateway_method.method.http_method}${aws_api_gateway_resource.resource.path}"
}

resource "aws_cloudwatch_log_group" "api_gw" {
  name = "/aws/api_gw/${aws_api_gateway_rest_api.api.name}"
  retention_in_days = 30
}

resource "aws_api_gateway_api_key" "reminders_key" {
  name = "terraform-reminders-key"
}

resource "aws_api_gateway_usage_plan" "usage_plan" {
  name         = "terraform-reminders-usage-plan"
  description  = "Terraform reminders usage plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.api.id
    stage  = aws_api_gateway_stage.prod.stage_name
  }
}

resource "aws_api_gateway_usage_plan_key" "usage_plan_key" {
  key_id        = aws_api_gateway_api_key.reminders_key.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.usage_plan.id
}