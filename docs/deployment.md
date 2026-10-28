# Azure VM deployment

One Ubuntu 24.04 x64 VM runs Caddy/React, the .NET API, the frozen-model Python service and PostgreSQL through Docker Compose. Only Caddy publishes ports. An Azure public-IP DNS name provides the hostname for HTTPS; keep `VITE_API_BASE_URL` empty so authentication stays on the same origin. This deployment uses PostgreSQL on the VM; a separate Neon database is not required.

## 1. Create the server (Azure portal)

Create a VM under the intended subscription with Ubuntu Server 24.04 LTS x64, 2 vCPUs and 4 GiB RAM (for example, `Standard_B2als_v2`), a 64 GiB Standard SSD LRS OS disk, and SSH public-key authentication. Use `azureuser` as the administrator name. Keep Spot, load balancing and optional paid monitoring services off for this single-server deployment.

Check Policy > Assignments > Allowed resource deployment regions before choosing a region for a student subscription. VM-family availability and quotas must also permit the selected size. Review compute, disk and public-IP costs; student credit pays for usage until depleted or expired, rather than guaranteeing a year of continuous hosting.

If Azure generates the SSH key, download `stewardlab-key.pem` when creating the VM. Keep it private and outside the repository. On Windows, the private key must be owned by your account and inaccessible to other ordinary users or groups.

Use the VM's network security group to allow TCP 22 from your laptop's public IP only (`YOUR_IP/32`), and TCP 80 and 443 from the internet. Keep outbound traffic enabled for package downloads and certificate issuance. PostgreSQL and Python have no public port mappings. Update the SSH source rule if your laptop's public IP changes.

Connect from PowerShell, replacing the address:

```powershell
ssh -i "$env:USERPROFILE\Downloads\stewardlab-key.pem" azureuser@YOUR_SERVER_IP
```

Check the SSH host fingerprint against the server information available through the provider console when establishing trust for the first connection.

## 2. Create the hostname (Azure portal)

Open the VM's public-IP resource > Configuration. Keep the IP assignment Static, enter an available DNS name label, and save. Copy the full DNS name from Overview, for example `your-label.southafricanorth.cloudapp.azure.com`. Use the exact generated name, including any extra segment Azure adds. No purchased domain or separate DNS zone is required.

Reference: https://learn.microsoft.com/en-us/azure/virtual-machines/create-fqdn

## 3. Install Docker (Ubuntu terminal)

The following commands run on the server, not in PowerShell. They use Docker's official Ubuntu package repository.

```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl git openssl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker run --rm hello-world
sudo docker compose version
```

Reference: https://docs.docker.com/engine/install/ubuntu/

## 4. Get the deployment source

### Configure verification email before deploying

Signup requires Azure Communication Services Email. Email is submitted over HTTPS, so no SMTP port needs to be opened on the VM.

1. In Azure, create an **Email Communication Services** resource (for example, `stewardlab-email`) in the student subscription and `stewardlab-rg` resource group. Note its Data location/geography.
2. Open the resource and choose **Add a free Azure subdomain**, or **Provision domains > Add domain > Azure domain**. After provisioning, copy the domain's exact **MailFrom** sender address.
3. Create a **Communication Services** resource (for example, `stewardlab-communication`) using the same Data location/geography. In **Email > Domains > Connect domain**, connect the provisioned email domain.
4. Under the Communication Services resource's **Keys**, copy its connection string privately. This is the Communication Services connection string, not a PostgreSQL connection string.

Azure provides the sending domain, so a purchased domain is not required. Email sending has usage charges and provider quotas; check the subscription's displayed pricing. References: [managed domain setup](https://learn.microsoft.com/en-us/azure/communication-services/quickstarts/email/add-azure-managed-domains), [domain connection](https://learn.microsoft.com/en-us/azure/communication-services/quickstarts/email/connect-email-communication-resource).

The settings below must be configured before the updated app is started. Missing email settings fail closed: registration and verification-email delivery return an unavailable response, without activating accounts. There is no production console-code or verification bypass.

### Publish and download the source

Commit and push the deployment changes from the laptop first so they exist in the remote branch. Review the diff before committing; include the Dockerfiles, Compose/Caddy configuration, deployment tests and API hosting changes. Do not commit `.env`, private keys or database backups.

On the server:

```bash
sudo install -d -o azureuser -g azureuser -m 0755 /opt/stewardlab
git clone https://github.com/noel-odero/Capstone-101.git /opt/stewardlab
cd /opt/stewardlab
git rev-parse --short HEAD
```

If this directory already contains the checkout, use it and pull the intended release instead of cloning over it.

Create the production environment file once. This block retains an existing configuration:

```bash
umask 077
if [ -e .env ]; then
  echo 'Existing .env retained. Edit it only if needed.'
else
  read -rp 'Public hostname (without https://): ' app_domain
  printf 'DOMAIN=%s\nPOSTGRES_PASSWORD=%s\n' "$app_domain" "$(openssl rand -hex 32)" > .env
  unset app_domain
fi
sudo docker compose config --quiet
```

The password is a random hexadecimal string, avoiding connection-string and Compose interpolation ambiguity. Keep it unchanged when reusing the database volume. Avoid printing the full resolved Compose configuration because it contains this password.

Edit `.env` privately with `nano .env` and add these settings using the actual values from Azure:

```text
VERIFICATION_EMAIL_CONNECTION_STRING=endpoint=https://YOUR_RESOURCE.communication.azure.com/;accesskey=YOUR_KEY
VERIFICATION_EMAIL_SENDER_ADDRESS=YOUR_EXACT_MAILFROM_ADDRESS
```

Keep the existing `DOMAIN` and `POSTGRES_PASSWORD` lines. Save the file, run `chmod 600 .env`, and validate with `sudo docker compose config --quiet`. Do not share screenshots of these values or commit this file. Local development uses the equivalent API environment variables `VerificationEmail__ConnectionString` and `VerificationEmail__SenderAddress`.

## 5. Build, migrate and start

```bash
cd /opt/stewardlab
sudo docker compose --parallel 1 build
sudo docker compose up -d --wait postgres
sudo docker compose --profile tools run --rm migrate
sudo docker compose up -d --wait
sudo docker compose ps
```

The first build downloads the scientific runtime and .NET SDK and can take several minutes. Building one image at a time reduces peak memory use on the 4 GB server. Resolve a migration failure before starting the application. The migration bundle updates schema without requiring the SDK on the running server.

The API waits for model and database health checks; Caddy waits for API readiness. Named volumes retain PostgreSQL data, authentication keys and certificates. Python contains the selected checkpoints, manifests and required scientific data, verified at startup. No training is performed.

Caddy obtains an HTTPS certificate once DNS resolves to this server and ports 80/443 are reachable. Inspect progress with:

```bash
sudo docker compose logs --tail=80 web
sudo docker compose logs --tail=80 api model
```

## 6. Check the public application

Replace the example hostname:

```bash
curl -fsS https://your-label.southafricanorth.cloudapp.azure.com/api/v1/health
curl -fsS https://your-label.southafricanorth.cloudapp.azure.com/api/v1/auth/session
```

Health should report `ready: true`; the second request should return an anonymous session. Open the HTTPS URL, create a demo account, save a synthetic sample, run the three-strategy comparison and reopen it through History. Check the original 3D page and Insights, then refresh a nested route to confirm the SPA fallback works.

During signup, check a real inbox for the six-digit code and verify it before opening the workspace. Codes last ten minutes, allow five failed attempts, and can be replaced once per minute, up to five sends per recipient per hour. The server stores tickets and codes only as hashes; the requesting browser keeps its opaque ticket in session storage to resume after reload. Resend/attempt limits persist in PostgreSQL. A pending signup does not create an active user or overwrite an existing account. Email-provider acceptance is not proof of inbox delivery; use Azure delivery diagnostics if a message does not arrive.

The email-verification migration leaves existing accounts unverified and invalidates their old cookie sessions. Existing researchers sign in with their original password, receive a code, and verify once. Their user IDs, samples and saved analyses remain unchanged. Subsequent sign-ins use email and password; this is ownership verification, not MFA at every login.

Restart the API and confirm the browser remains signed in and saved records remain available:

```bash
sudo docker compose restart api
```

Only Caddy's address `172.30.72.10` is trusted to forward client IP and HTTPS information. If the Docker subnet conflicts with an existing network, choose another subnet and update both the trusted address and Compose edge network together.

## 7. Back up the database

```bash
cd /opt/stewardlab
sudo bash deploy/backup.sh
```

Schedule a daily backup at 03:00 UTC on a server using UTC:

```bash
sudo tee /etc/cron.d/stewardlab-backup > /dev/null <<'EOF'
0 3 * * * root /usr/bin/flock -n /run/lock/stewardlab-backup.lock /bin/bash /opt/stewardlab/deploy/backup.sh >> /var/log/stewardlab-backup.log 2>&1
EOF
sudo chmod 0644 /etc/cron.d/stewardlab-backup
```

Backups are written under `/opt/stewardlab/backups/`, excluded from Git and image builds. The scheduled job runs as root and creates private backup files. To download a particular backup with `scp` as `azureuser`, first use `sudo chown azureuser:azureuser /opt/stewardlab/backups/EXACT_BACKUP_FILENAME.dump` for that file, retaining its private permissions. Copy backups to a protected folder off the VM. A local backup does not cover loss of the server. Keep the production environment and authentication keys recoverable as well.

Test a dump in a separate database before relying on it. Restoring over the live database replaces data and needs a deliberate maintenance/recovery plan.

## 8. Update the application

```bash
cd /opt/stewardlab
sudo bash deploy/backup.sh
git pull --ff-only
sudo docker compose --parallel 1 build
sudo docker compose stop api web
sudo docker compose --profile tools run --rm migrate
sudo docker compose up -d --wait
sudo docker compose ps
```

This is a single-server deployment with a maintenance window. Named volumes are reused. Use `docker compose down` without the volume-removal option to retain stored records. After a failed migration, investigate before restarting or rolling back; changing images alone does not reverse schema changes.
