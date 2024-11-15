# Use the official PostgreSQL image as a base
FROM postgres:16.4

# Install dependencies
RUN apt-get update && \
    apt-get install -y postgresql-server-dev-all build-essential git

# Clone and install the RUM extension
RUN git clone https://github.com/postgrespro/rum.git && \
    cd rum && \
    make USE_PGXS=1 && \
    make USE_PGXS=1 install

# Clean up
RUN apt-get remove -y build-essential git && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* rum

# Expose the PostgreSQL port
EXPOSE 5432
