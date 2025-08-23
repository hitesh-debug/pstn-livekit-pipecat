# ==== CONFIG ====
export REGION=us-east-1    # set if not already
export CLUSTER="lk-agents"
export SERVICE="lk-agent"
export FAMILY="lk-agent"                      # task def family
export CONTAINER="lk-agent"                   # container name inside task def
export REPO="lk-agent"                        # ECR repo name
export DOCKERFILE="services/agent/Dockerfile" # adjust if your Dockerfile is elsewhere

# Good unique tag: timestamp + short git sha (falls back to 'manual')
export IMAGE_TAG="$(date +%Y%m%d%H%M)-$(git rev-parse --short HEAD 2>/dev/null || echo manual)"

# ==== PREP ====
aws sts get-caller-identity --query Account --output text >/dev/null
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create ECR repo if missing (ignore error if it exists)
aws ecr create-repository --repository-name "$REPO" --region "$REGION" 2>/dev/null || true

# Login docker to ECR
aws ecr get-login-password --region "$REGION" \
| docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

# ==== BUILD (force linux/amd64 if you're on Apple Silicon) ====
# If on Mac M-series, use buildx line; otherwise regular docker build works.
# Regular:
docker build -f "$DOCKERFILE" -t "$REPO:$IMAGE_TAG" .
# Or on Apple Silicon:
# docker buildx build --platform linux/amd64 -f "$DOCKERFILE" -t "$REPO:$IMAGE_TAG" .

# Tag & push to ECR
docker tag "$REPO:$IMAGE_TAG" "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO:$IMAGE_TAG"
docker push "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO:$IMAGE_TAG"

# ==== REGISTER NEW TASK DEF REVISION WITH NEW IMAGE ====
# Grab current task def JSON, strip read-only fields, and swap image
aws ecs describe-task-definition --task-definition "$FAMILY" --region "$REGION" \
  --query 'taskDefinition' > td.json

# Remove fields ECS won’t accept on register
jq 'del(.taskDefinitionArn,.revision,.status,.requiresAttributes,.compatibilities,.registeredAt,.registeredBy,.deregisteredAt,.inferenceAccelerators,.runtimePlatform?.cpuArchitecture,.runtimePlatform?.operatingSystemFamily)
    | .containerDefinitions |= (map(if .name=="'"$CONTAINER"'
                                    then .image="'"$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO:$IMAGE_TAG"'"
                                    else .
                                   end))' td.json > td.new.json

# (Optional) bump resources here too:
# jq '.cpu="512" | .memory="1024"' td.new.json > td.new.json

NEW_REV=$(aws ecs register-task-definition \
  --cli-input-json file://td.new.json --region "$REGION" \
  --query 'taskDefinition.revision' --output text)

echo "Registered $FAMILY revision: $NEW_REV"

# ==== DEPLOY TO SERVICE ====
aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "$SERVICE" \
  --task-definition "$FAMILY:$NEW_REV" \
  --region "$REGION" \
  --query 'service.{status:status, taskDef:taskDefinition, desired:desiredCount, running:runningCount}'

# If you reuse the same tag later, add: --force-new-deployment

# ==== WAIT UNTIL STABLE & CHECK EVENTS ====
aws ecs wait services-stable --cluster "$CLUSTER" --services "$SERVICE" --region "$REGION"
aws ecs describe-services \
  --cluster "$CLUSTER" --services "$SERVICE" --region "$REGION" \
  --query 'services[0].events[0:5].message'

# ==== (Optional) TAIL LOGS ====
# Find the latest stopped/running task and view CloudWatch logs per your log group/stream naming.
TASK_ARN=$(aws ecs list-tasks --cluster "$CLUSTER" --service-name "$SERVICE" --region "$REGION" --desired-status RUNNING --query 'taskArns[-1]' --output text)
echo "Running task: $TASK_ARN"
