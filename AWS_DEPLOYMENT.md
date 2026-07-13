# CareerPilot — AWS Deployment Guide

Deploys CareerPilot on **EC2 + S3 + IAM**, scoped to stay inside the free-tier credit window (new-account $200 credit / 6-month clock). Follow in order.

---

## 0. Before you start — set a budget alarm

Do this first, before creating anything else, so you have a safety net from minute one.

1. Go to **AWS Billing → Budgets → Create budget**.
2. Choose **Cost budget**, set a monthly amount (e.g. $10), and add an alert at 80% of that.
3. Enter an email for the alert. This costs nothing and takes 2 minutes.

```bash
# Or via CLI:
aws budgets create-budget --account-id <YOUR_ACCOUNT_ID> \
  --budget file://budget.json --notifications-with-subscribers file://notifications.json
```

---

## 1. Create the S3 bucket

```bash
aws s3api create-bucket \
  --bucket careerpilot-<your-unique-suffix> \
  --region us-east-1

# Block all public access — this bucket holds resumes, keep it private
aws s3api put-public-access-block \
  --bucket careerpilot-<your-unique-suffix> \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

---

## 2. Create the IAM policy + role (least privilege)

**`s3-policy.json`** — scoped to only this bucket, only the actions the app needs:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::careerpilot-<your-unique-suffix>/*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::careerpilot-<your-unique-suffix>"
    }
  ]
}
```

```bash
aws iam create-policy \
  --policy-name CareerPilotS3Access \
  --policy-document file://s3-policy.json

aws iam create-role \
  --role-name CareerPilotEC2Role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ec2.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

aws iam attach-role-policy \
  --role-name CareerPilotEC2Role \
  --policy-arn arn:aws:iam::<YOUR_ACCOUNT_ID>:policy/CareerPilotS3Access

aws iam create-instance-profile --instance-profile-name CareerPilotEC2Profile
aws iam add-role-to-instance-profile \
  --instance-profile-name CareerPilotEC2Profile \
  --role-name CareerPilotEC2Role
```

**Why this matters (and why it's worth naming on your resume):** the EC2 instance assumes this role automatically — the app never stores an AWS access key/secret anywhere. `boto3`'s default credential chain picks up the role's temporary credentials from the instance metadata service. This is the standard production pattern, not a shortcut.

---

## 3. Security group

Only allow what's needed — SSH from your IP only, HTTP(S) from anywhere for the app:

```bash
aws ec2 create-security-group \
  --group-name careerpilot-sg \
  --description "CareerPilot app access"

aws ec2 authorize-security-group-ingress \
  --group-name careerpilot-sg \
  --protocol tcp --port 22 --cidr <YOUR_IP>/32

aws ec2 authorize-security-group-ingress \
  --group-name careerpilot-sg \
  --protocol tcp --port 80 --cidr 0.0.0.0/0
```

(Streamlit runs on 8501 by default — either open 8501 directly for simplicity, or reverse-proxy it through Nginx on port 80, shown in step 6.)

---

## 4. Launch the EC2 instance

```bash
aws ec2 run-instances \
  --image-id <FREE_TIER_ELIGIBLE_AMI_ID> \
  --instance-type t3.micro \
  --iam-instance-profile Name=CareerPilotEC2Profile \
  --security-groups careerpilot-sg \
  --key-name <your-keypair> \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=careerpilot}]'
```

Confirm the AMI you pick is flagged free-tier-eligible:
```bash
aws ec2 describe-images --filters Name=free-tier-eligible,Values=true --query "Images[*].[ImageId,Name]" --output text | grep -i ubuntu
```

---

## 5. On the instance — install and configure

```bash
ssh -i <your-keypair>.pem ubuntu@<instance-public-ip>

sudo apt update && sudo apt install -y python3-pip python3-venv nginx git
git clone <your-github-repo-url> careerpilot
cd careerpilot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# .env only needs the Gemini key + bucket name — NOT AWS credentials (the instance role handles that)
cp .env.example .env
nano .env   # set GOOGLE_API_KEY and S3_BUCKET_NAME
```

---

## 6. Run as a service (systemd) + reverse proxy

**`/etc/systemd/system/careerpilot.service`:**
```ini
[Unit]
Description=CareerPilot Streamlit App
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/careerpilot
Environment="PATH=/home/ubuntu/careerpilot/venv/bin"
ExecStart=/home/ubuntu/careerpilot/venv/bin/streamlit run app.py --server.port 8501 --server.address 0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable careerpilot
sudo systemctl start careerpilot
```

**Nginx reverse proxy** (`/etc/nginx/sites-available/careerpilot`):
```nginx
server {
    listen 80;
    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/careerpilot /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

Visit `http://<instance-public-ip>` — the app should be live.

---

## 7. Cost hygiene checklist

- [ ] Budget alarm set (step 0)
- [ ] Instance type is `t3.micro` (free-tier eligible)
- [ ] No Elastic IP allocated-but-unattached (if you allocate one, attach it or release it)
- [ ] Stop the instance (`aws ec2 stop-instances --instance-ids <id>`) when not actively demoing — doesn't delete anything, just stops billing compute hours
- [ ] S3 bucket has public access blocked (step 1)
- [ ] No NAT Gateway created (not needed here — don't let a tutorial talk you into a private subnet for this)

---

## 8. What to say about this on your resume/interview

This setup demonstrates: IAM least-privilege role design (no hardcoded credentials), private S3 storage for sensitive documents, security-group scoping, and running a Python app as a managed systemd service behind Nginx — a realistic small-scale production deployment pattern, not just "I clicked deploy."
