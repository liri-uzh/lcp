# Use the official PostgreSQL image as a base
FROM postgres:17.0

# Install dependencies
RUN apt-get update && \
    apt-get install -y postgresql-server-dev-17 build-essential git

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
