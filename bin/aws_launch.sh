#!/usr/bin/env bash
# aws_launch.sh — launch the rockauto-swarm EC2. RUN IN AWS CloudShell (admin/root).
#
# Creates an IAM instance role (API Gateway + SSM), then launches an Ubuntu box that
# self-provisions (deps + clone) and AUTO-STARTS the crawl swarm on boot. No SSH keys:
# the box gets AWS creds from the role, and you/I monitor + control it via SSM. Falls
# back to smaller instance types if the account's vCPU quota rejects the biggest.
#
#   git clone https://github.com/ahmerfr/rockauto-crawler.git
#   bash rockauto-crawler/bin/aws_launch.sh
set -euo pipefail
REGION=us-east-1
NAME=rockauto-swarm
ROLE=rockauto-crawler
DISK_GB=100
# biggest first; WORKERS scaled to each box's RAM (~150MB/worker)
TYPES=(c7i.8xlarge c7i.4xlarge c7i.2xlarge)
declare -A W=( [c7i.8xlarge]=200 [c7i.4xlarge]=110 [c7i.2xlarge]=50 )

echo "== 1. resolve newest Ubuntu 24.04 amd64 AMI =="
AMI=$(aws ec2 describe-images --region "$REGION" --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd*/ubuntu-*-24.04-amd64-server-*" \
            "Name=state,Values=available" "Name=architecture,Values=x86_64" \
  --query 'sort_by(Images,&CreationDate)[-1].ImageId' --output text)
echo "   AMI=$AMI"

echo "== 2. IAM role $ROLE (API Gateway + SSM) =="
if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE" --assume-role-policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  aws iam attach-role-policy --role-name "$ROLE" --policy-arn arn:aws:iam::aws:policy/AmazonAPIGatewayAdministrator
  aws iam attach-role-policy --role-name "$ROLE" --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
  aws iam create-instance-profile --instance-profile-name "$ROLE" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$ROLE" --role-name "$ROLE"
  echo "   created; waiting 15s for IAM propagation"; sleep 15
else
  echo "   role already exists, reusing"
fi

echo "== 3. security group + default subnets by AZ =="
SG=$(aws ec2 describe-security-groups --region "$REGION" --filters "Name=group-name,Values=default" \
  --query 'SecurityGroups[0].GroupId' --output text)
declare -A AZSUB
while read -r sid az; do AZSUB[$az]=$sid; done < <(aws ec2 describe-subnets --region "$REGION" \
  --filters "Name=default-for-az,Values=true" --query 'Subnets[].[SubnetId,AvailabilityZone]' --output text)
echo "   SG=$SG  default subnets in AZs: ${!AZSUB[*]}"

echo "== 4. launch (biggest type, in an AZ that offers it) =="
IID=""
for T in "${TYPES[@]}"; do
  WK=${W[$T]}
  # not every AZ offers newer instance types (us-east-1e lacks c7i) — pick an AZ that does
  SUBNET=""
  for az in $(aws ec2 describe-instance-type-offerings --region "$REGION" \
        --location-type availability-zone --filters "Name=instance-type,Values=$T" \
        --query 'InstanceTypeOfferings[].Location' --output text); do
    if [ -n "${AZSUB[$az]:-}" ]; then SUBNET=${AZSUB[$az]}; break; fi
  done
  [ -z "$SUBNET" ] && { echo "   no default subnet in an AZ offering $T, skipping"; continue; }
  echo "   $T -> subnet $SUBNET"
  cat > /tmp/ud.sh <<EOF
#!/bin/bash
set -x
apt-get update -y
apt-get install -y python3-pip python3-venv git
cd /home/ubuntu
git clone https://github.com/ahmerfr/rockauto-crawler.git
cd rockauto-crawler
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install requests lxml beautifulsoup4 boto3 requests-ip-rotator
mkdir -p logs out fr
chown -R ubuntu:ubuntu /home/ubuntu
sudo -u ubuntu bash -c 'cd /home/ubuntu/rockauto-crawler && PY=./venv/bin/python WORKERS=$WK nohup bash bin/crawl_apigw_fleet.sh > logs/fleet.log 2>&1 &'
echo done > /home/ubuntu/PROVISION_DONE
EOF
  echo "   trying $T (WORKERS=$WK)..."
  if IID=$(aws ec2 run-instances --region "$REGION" --image-id "$AMI" --instance-type "$T" \
      --iam-instance-profile "Name=$ROLE" \
      --network-interfaces "DeviceIndex=0,SubnetId=$SUBNET,Groups=$SG,AssociatePublicIpAddress=true,DeleteOnTermination=true" \
      --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=$DISK_GB,VolumeType=gp3}" \
      --user-data file:///tmp/ud.sh \
      --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME}]" \
      --query 'Instances[0].InstanceId' --output text 2>/tmp/err.txt); then
    echo "   LAUNCHED $T => $IID"; CHOSEN=$T; break
  else
    echo "   $T failed: $(head -c 240 /tmp/err.txt)"; IID=""
  fi
done
[ -z "${IID:-}" ] && { echo "ALL TYPES FAILED — likely On-Demand vCPU quota. Request an increase."; exit 1; }

echo "== 5. wait for running =="
aws ec2 wait instance-running --region "$REGION" --instance-ids "$IID"
IP=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$IID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "==================== LAUNCHED ===================="
echo " InstanceId : $IID"
echo " Type       : $CHOSEN  (WORKERS=${W[$CHOSEN]})"
echo " PublicIP   : $IP"
echo " Boot provisioning (deps + clone + crawl auto-start) runs ~3-6 min."
echo " Monitor via SSM (no SSH):"
echo "   aws ssm send-command --instance-ids $IID --document-name AWS-RunShellScript \\"
echo "     --parameters 'commands=[\"tail -30 /home/ubuntu/rockauto-crawler/logs/w0.log\"]' \\"
echo "     --query Command.CommandId --output text"
echo "================================================="
