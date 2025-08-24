REGION=us-east-1
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
CLUSTER=lk-agents
SERVICE=lk-agent

# aws ecr create-repository --repository-name lk/agent --region $REGION || true

# # Build & push (from repo root)
# docker build -t lk/agent:latest ./services/agent
# docker tag lk/agent:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/lk/agent:latest
# aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com
# docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/lk/agent:latest

# aws ecs create-cluster --cluster-name lk-agents --region $REGION || true

# Task execution role (pull images, write logs)
# aws iam create-role --role-name ecsTaskExecutionRole \
#   --assume-role-policy-document '{
#     "Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]
#   }' || true
# aws iam attach-role-policy --role-name ecsTaskExecutionRole \
#   --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy || true

# # Agent task role (read secrets if you need; optional)
# aws iam create-role --role-name lkAgentTaskRole \
#   --assume-role-policy-document '{
#     "Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]
#   }' || true


# cat > agent-td.json <<JSON
# {
#   "family": "lk-agent",
#   "cpu": "256",
#   "memory": "512",
#   "networkMode": "awsvpc",
#   "requiresCompatibilities": ["FARGATE"],
#   "executionRoleArn": "arn:aws:iam::$ACCOUNT_ID:role/ecsTaskExecutionRole",
#   "taskRoleArn":       "arn:aws:iam::$ACCOUNT_ID:role/lkAgentTaskRole",
#   "containerDefinitions": [{
#     "name": "agent",
#     "image": "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/lk/agent:latest",
#     "essential": true,
#     "command": ["python","agent.py"],
#     "workingDirectory": "/app",
#     "environment": [
#       { "name": "LIVEKIT_URL", "value": "wss://YOUR_SUBDOMAIN.livekit.cloud" }
#     ],
#     "logConfiguration": {
#       "logDriver": "awslogs",
#       "options": {
#         "awslogs-group": "/ecs/lk-agent",
#         "awslogs-region": "$REGION",
#         "awslogs-stream-prefix": "ecs"
#       }
#     }
#   }]
# }
# JSON
# aws logs create-log-group --log-group-name /ecs/lk-agent --region $REGION || true
# aws ecs register-task-definition --cli-input-json file://agent-td.json --region $REGION

# VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query "Vpcs[0].VpcId" --output text)
# SUBNETS=$(aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC_ID Name=default-for-az,Values=true \
#   --query "Subnets[].SubnetId" --output text)
# # pick 2 subnets:
# S1=$(echo $SUBNETS | awk '{print $1}'); S2=$(echo $SUBNETS | awk '{print $2}')
# # security group (egress open)
# SG_ID=$(aws ec2 create-security-group --group-name lk-agents-sg --description "lk agents" --vpc-id $VPC_ID --output text)
# aws ec2 authorize-security-group-egress --group-id sg-00a49f95b64b56864 --ip-permissions IpProtocol=-1,IpRanges='[{CidrIp=0.0.0.0/0}]' || true

# brew install cloudflared && 

# sudo cloudflared service install eyJhIjoiOGRjOWY1ODE0YjlmZDBmNWFiNTM3ZWNjZmI4ZmM4MjciLCJ0IjoiZDA4MGUxMDEtZDc4MS00MjYyLThkMmQtMjJmMDdmMmZkMTIyIiwicyI6IlltRmlOR0kyWkRRdE1UazNPQzAwTldObExUbGxNMkV0WmpnNE5XRTRZemxqTmpZeiJ9


# docker tag lk/agent:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/lk/agent:latest

# aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com
# docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/lk/agent:latest

# aws ecs register-task-definition \
#   --cli-input-json file://agent-td.json \
#   --region $REGION

  # latest ACTIVE task-def ARN (includes :revision)
# aws ecs create-cluster --cluster-name lk-agents --region $REGION || true

# VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query "Vpcs[0].VpcId" --output text --region $REGION)
# SUBNETS=$(aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC_ID Name=default-for-az,Values=true --query "Subnets[].SubnetId" --output text --region $REGION)
# S1=$(echo $SUBNETS | awk '{print $1}'); S2=$(echo $SUBNETS | awk '{print $2}')

# SG_ID=$(aws ec2 create-security-group \
#   --group-name lk-agents-sg \
#   --description "lk agents egress" \
#   --vpc-id $VPC_ID --query GroupId --output text --region $REGION)
# aws ec2 authorize-security-group-egress --group-id $SG_ID \
#   --ip-permissions IpProtocol=-1,IpRanges='[{CidrIp=0.0.0.0/0}]' \
#   --region $REGION || true

# echo "SUBNETS: $S1,$S2"
# echo "SECURITY_GROUP: $SG_ID"

# aws ecs describe-clusters \
#   --clusters "lk-agents" --include CAPACITY_PROVIDERS,SETTINGS \
#   --region "$REGION" \
#   --query 'clusters[0].{Providers:capacityProviders,Default:defaultCapacityProviderStrategy}'

# # add FARGATE and FARGATE_SPOT; make SPOT the default if you like
# aws ecs put-cluster-capacity-providers \
#   --cluster "lk-agents" \
#   --capacity-providers FARGATE FARGATE_SPOT \
#   --default-capacity-provider-strategy capacityProvider=FARGATE_SPOT,weight=1 \
#   --region "$REGION"
# FAMILY=lk-agent
# aws ecs describe-task-definition --region "$REGION" \
#   --task-definition "$FAMILY" --query 'taskDefinition' > td.json

# # Add runtimePlatform + remove read-only fields
# jq 'del(.status,.taskDefinitionArn,.requiresAttributes,.revision,.compatibilities,.registeredAt,.registeredBy)
#   | .runtimePlatform = {"cpuArchitecture":"ARM64","operatingSystemFamily":"LINUX"}' td.json > td-arm.json

# NEW_TD_ARN=$(aws ecs register-task-definition \
#   --region "$REGION" --cli-input-json file://td-arm.json \
#   --query 'taskDefinition.taskDefinitionArn' --output text)

# TD_ARN=$(aws ecs list-task-definitions \
#   --region "$REGION" --family-prefix lk-agent --status ACTIVE --sort DESC --max-results 1 \
#   --query 'taskDefinitionArns[0]' --output text)
# echo "$TD_ARN"

# aws ecs update-service --region "$REGION" \
#   --cluster "$CLUSTER" --service "$SERVICE" \
#   --task-definition "arn:aws:ecs:us-east-1:820178563918:task-definition/lk-agent:5"

# aws ecs register-task-definition \
#   --cli-input-json file://agent-td.json \
#   --region $REGION

# set your region and family
# REGION=us-east-1
FAMILY=lk-agent

# # Latest ACTIVE revision (deployable)
# TD_ARN=$(aws ecs list-task-definitions \
#   --region "$REGION" --family-prefix "$FAMILY" \
#   --status ACTIVE --sort DESC --max-results 1 \
#   --query 'taskDefinitionArns[0]' --output text)
# echo "$TD_ARN"              # arn:aws:ecs:...:task-definition/lk-agent:42
# echo "${TD_ARN##*:}"        # 42 (just the number)

# # Or: ask ECS directly for the latest ACTIVE and get the number
# REV=$(aws ecs describe-task-definition \
#   --region "$REGION" --task-definition "$FAMILY" \
#   --query 'taskDefinition.revision' --output text)
# echo "$REV"                 # 42

# # If you want "family:rev" in one go
# aws ecs describe-task-definition \
#   --region "$REGION" --task-definition "$FAMILY" \
#   --query 'join(`:`, [taskDefinition.family, to_string(taskDefinition.revision)])' \
#   --output text
# export REPO=lk/agent
# # export TAG=$(git rev-parse --short HEAD || date +%Y%m%d%H%M%S)
# export IMAGE="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO"

# # aws ecr get-login-password --region "$REGION" \
# # | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

# # build multi-arch so it runs on both amd64/arm64
# # docker buildx create --use >/dev/null 2>&1 || true
# # docker buildx build --platform linux/amd64,linux/arm64 -t "$IMAGE" --push .

# docker build -f services/agent/Dockerfile -t "$IMAGE" services/agent
# docker tag "$IMAGE" "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO:latest"
# docker push "$IMAGE"