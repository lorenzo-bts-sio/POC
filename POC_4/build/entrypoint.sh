#!/bin/sh

# Create the sftp user group
addgroup -S sftp
mkdir -p "/sftp/data/in"
mkdir -p "/sftp/data/out"

# Function to create each user
create_user() {
    local username="$1"
    adduser -D -s /sbin/nologin --no-create-home -G sftp "$username"
    PASSWD=$(date | md5sum | cut -c1-18)
    echo "$username:$PASSWD" | chpasswd
}

# Loop through the environment variables to create users
for var in $(env | grep USER); do
    username=$(echo "$var" | cut -d = -f2)
    create_user "$username"
done

chown -R root:sftp /sftp/data/
chmod  755 /sftp/data
chmod  775 /sftp/data/in
chmod  775 /sftp/data/out
chmod  660 /exporter.py


# Start the exporter server and SSHD in exporter
exec python3 /exporter.py


