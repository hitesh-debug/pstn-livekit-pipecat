REGION=us-east-1
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

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
# # aws ecs register-task-definition --cli-input-json file://agent-td.json --region $REGION

# VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query "Vpcs[0].VpcId" --output text)
# SUBNETS=$(aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC_ID Name=default-for-az,Values=true \
#   --query "Subnets[].SubnetId" --output text)
# # pick 2 subnets:
# S1=$(echo $SUBNETS | awk '{print $1}'); S2=$(echo $SUBNETS | awk '{print $2}')
# # security group (egress open)
# SG_ID=$(aws ec2 create-security-group --group-name lk-agents-sg --description "lk agents" --vpc-id $VPC_ID --output text)
# aws ec2 authorize-security-group-egress --group-id sg-00a49f95b64b56864 --ip-permissions IpProtocol=-1,IpRanges='[{CidrIp=0.0.0.0/0}]' || true
