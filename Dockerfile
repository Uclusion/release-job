FROM ubuntu:latest

# Update the package list and install Python 3
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN pip install PyGithub

COPY entrypoint.py /usr/local/bin/entrypoint.py

# Make the entrypoint.py executable
RUN chmod +x /usr/local/bin/entrypoint.py

# Set the entrypoint for your container
ENTRYPOINT ["/usr/local/bin/entrypoint.py"]