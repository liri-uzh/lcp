# LiRI Corpus Platform (LCP)

> A Python/vue.js/PostgreSQL-based web-application for querying large and/or multimodal corpora

## Context

Our aim is to build a platform that can facilitate uploading, display and querying of diverse corpora. This means that a single backend should be used in tandem with one of a number of possible frontends, with each frontend customised for a specific use-case (large text corpora, video corpora, etc).

We will be serving an instance of the app [here](https://lcp.test.linguistik.uzh.ch/) (which is currently in alpha, with certain corpora/features requiring SWITCH/edu-id credentials), but it is also (theoretically) possible to run your own instance of the entire app, with your own authentication logic and database.

## Using our deployed version

We aim to provide an 'authoritative' deployment of the system (including its various frontends), where you can upload, share and access your corpora via both web and API interfaces. Full documentation of the app is a work in progress, to be served [here](https://liri.linguistik.uzh.ch/wiki/langtech/lcp/start).

## Installing the system locally

You will need:

* This repo and its submodules
* Python 3.11
* Node/NPM/vue.js
* PostgreSQL
* Redis

The simplest way to setup your own instance is to install it into your home folder, in a directory called `lcp`. So enter:

```
cd
```

to enter your home directory before anything else.

### Clone our codebases

Clone this repo and its submodules:

```bash
git clone --recurse-submodules https://github.com/liri-uzh/lcp.git
cd lcp
````

This will also clone any needed submodules; each should be available in the root of this repo.

### Installing Python3.11 / creating a virtual environment

Before installing any cloned code, install Python 3.11+ or setup a Python 3.11+ virtual environment. To make a virtual environment, you can do:

```bash
python3.11 -m venv ./lcp-venv
```

Finally activate the environment. Be sure to use activate this environment any time you want to use the app:

```bash
source ./lcp-venv/bin/activate
```

### Install the codebase

From the repo root dir you can do:

```python
pip install -e .
```

This makes various helper commands available on the system:

```bash
lcp-setup
```

This will create a `~/lcp/.env` with some default and some missing settings, which you can then edit/fill in as required.

You can also run:

```bash
lcp-frontend-setup
```

to install the frontend (assuming you have node.js and NPM installed).

### Configuring `.env`

We use a `.env` file to manage the backend configuration. Running the `lcp-setup` command should have created `~/lcp/.env`. If it's not there, copy `.env.example` as seen in this repo to your LCP directory:

```bash
cp .env.example ~/lcp/.env
```

When LCP is started, it will look in `~/lcp` for a `.env` file. If you didn't install into the home directory, hopefully it is smart enough to find a `.env` file in your current working directory. If it can't find either, it is unlikely to work.

#### `.env` settings

* You will need to provide `.env` with the location of your Redis/PostgeSQL instances, as well as the PostgreSQL database name (the defaults assume a default local installation of both PostgreSQL and Redis)
* Make sure the `IMPORT` related settings don't exceed your system's resources
* Comment out the `SSH_` variables if not using, or you'll get an SSH gateway error.
* If you don't want to use any authentication, make sure `AUTHENTICATION_CLASS` is empty. Otherwise, if you have a custom authentication class you wish to use, point to it:

```bash
AUTHENTICATION_CLASS=somecodedir.auth.Authentication
```

#### Authentication classes

Our app uses LAMa and SWITCH/edu-id for authentication. If you were running your own version, you may want no authentication, or a custom authentication system. For custom authentication, take a look at `lcpvian/authenticate.py`. The class you point to in `.env` will need to have the same methods, each returning booleans which indicate whether a user has access to a given resource.

### Installing the frontend manually

When you install the repo via `pip`, you should have access to commands like `lcp-install`, which can help install the system. However if you are a developer or want to install the frontend manually, the following information will be useful.

For the frontend, you need to install `Node.js`, `npm` and `yarn`. For Ubuntu, that would be something like:

```bash
sudo apt update
sudo apt install nodejs
sudo apt install npm
npm install --global yarn
```

You might need to install a specific version of node for compatibility concerns. As of August 9, 2023 the module `node-ipc` is incompatible with node 20+, so a sensible target version is 19. If you don't have `nvm` installed yet, you can install it from the `nvm-sh` github repo:

```bash
wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.4/install.sh | bash
```

Close then reopen the terminal to install node 19:

```bash
nvm install 19
```

You can now go back to lcpvian and use node 19:

```bash
cd lcpvian
nvm use 19
```

Then, if you haven't before, install the frontend:

```bash
cd frontend
yarn install
```

Then you can start it with:

```bash
# in ./frontend:
# for LCP frontend
yarn serve:lcp
# for videoscope frontend
yarn serve:videoscope
# for catchphrase frontend
yarn serve:catchphrase
# for soundscript frontend
yarn serve:soundscript
```

## Starting the app

Users of the open-source version can run the `lcp` command to start the app. Assuming everything is correctly configured, it will be available via the host/port configured in `.env`.

### Starting backend manually

The backend uses worker processes to handle long-running database jobs. Therefore, you need to start at least one worker via:

```bash
# uses c code if available, otherwise py:
python -m lcpvian worker
# to only use .py:
# python lcpvian/worker.py
```

Note that you can start as many as you want.

In another session, start the backend with:

```bash
python -m lcpvian
```

It will use C extension modules if they are compiled available, or else straight Python.

For the LAMa connection to work, you might need to do:

```bash
ssh -L 18080:192.168.1.57:8080 berlit.liri
```

The app will be available (by default) at `http://localhost:8080`.

## Development

When pulling latest code, you should also fetch the latest from the submodules. You can do it all in one command:

```bash
git pull --recurse-submodules
```

You might also want to configure `git` to push changes to submodules when you push to `lcpvian`:

```bash
git config --global push.recurseSubmodules "on-demand"
```

### Type checking

To check that typing is correct (do before commit/push/c-extension building):
```bash
mypy lcpvian
```

## Configuration

The defaults in `.env` should work for PostgreSQL and LAMa. Default Redis is local, so you should have a Redis instance running as per the URL specified in `.env`.

Some `.env` values that might need adjusting for deployment:

> `DEBUG`

When this is truthy (`true`, `1`), certain sensitive info can be passed to frontend for display in error messages or console. Usually, this is error tracebacks or SQL scripts. When `debug` is falsey, sensitive values are sanitised.

> `AIO_PORT`

The port that the backend runs on.

> `REDIS_DB_INDEX`

Setting as a positive integer allows us to switch between different Redis databases based on their index. `0` is fine for development.

> `QUERY_TIMEOUT`

In seconds, how long can a query be running until it gets stopped?

> `UPLOAD_TIMEOUT`

In seconds, how long can an upload job be running until it gets stopped (should be considerably longer!).

> `QUERY_TTL`

In seconds, how long should query data stay in Redis? If a user tries to change pages on a query older than this, the query needs to be rerun from the start. It should work, but the UX is much worse than fetching from Redis.

> `USE_CACHE`

Queries are stored by a key in Redis, and this key is a hash of the data needed to generate the query. Therefore, when a new query is created, we hash it to check that it hasn't already been performed. If it has, and if `USE_CACHE` is truthy, we retrieve the earlier data from Redis and send that to the user (who may be different from the one who generated the original query). You can disable this for debugging if the cache doesn't seem to be working correctly, but ideally it is switched on in production, as it provides a lot of performance benefit for common queries!

> `SQL_(QUERY|UPLOAD)_(USERNAME|PASSWORD)`

The app uses two SQL connections. The `QUERY` connection should not have write access. The `UPLOAD` connection should. Note that storing queries also requires write access.

> `IMPORT_MAX_CONCURRENT`

When importing a new corpus, how many concurrent tasks can be spawned? Set to `-1` or `0` for no limit, set to `1` for no concurrency, or larger to set the concurrency limit.

> `IMPORT_MAX_MEMORY_GB`

When processing concurrently, a lot of data can be read into memory for `COPY` tasks. If this amount of data is reached while building `COPY` tasks, we stop building tasks, execute the pending ones, and resume when they are done. Remember that if `IMPORT_MAX_CONCURRENT` is not `1`, the real memory usage could be multiplied by the number of concurrent tasks.

> `IMPORT_MAX_COPY_GB`

In GB, how much data can be read in one chunk for `COPY` tasks? Note that the limit can be exceeded by a few bytes in practice to complete an incomplete CSV line. Remember that if `IMPORT_MAX_CONCURRENT` is not 1, the real memory usage could be multiplied by the number of concurrent tasks.

> `UPLOAD_USE_POOL`

If truthy, a real connection pool will be used for the uploader (as well as any other jobs requiring write access to the DB). `IMPORT_MIN_NUM_CONNECTIONS` and `IMPORT_MAX_NUM_CONNECTIONS` will only be respected if this is switched on. If falsey, these values are ignored, as no connection pool is used for write jobs.

> `(QUERY|UPLOAD)_(MIN|MAX)_NUM_CONNECTIONS`

These four values control the number of connections in the connection pools. If `UPLOAD_USE_POOL` is `false`, these numbers are ignored for `UPLOAD`, because no pool exists.

> `POOL_NUM_WORKERS`

This number controls how many worker threads are spawned to perform setup/cleanup-type operations on connection pool(s). `3` is the default provided by `psycopg`.

> `SENTRY_DSN`

If set, exception logs are sent to Sentry. You probably want to leave it unset for development.

> `SENTRY_TRACES_SAMPLE_RATE`

A float value `1.0` or smaller, dictating the proportion of logs that get sent to sentry. Maybe we need to reduce this if one day our app is super popular, but `1.0` is fine for now.

> `MAX_SIMULTANEOUS_JOBS_PER_USER`

Currently not used; in theory if there are free resources we could allow a user to query multiple batches simultaneously. If we end up allowing simultaneous mode, this value can be used to limit how many jobs (i.e. queries over batches) can be run at once.

## Command line 'interface'

Once `lcpvian` is installed you can run a variety of commands via `python -m lcpvian`.

Start backend:

```bash
python -m lcpvian
```

Start worker:

```bash
python -m lcpvian worker
```

Convert DQD to JSON:

```bash
python -m lcpvian dqd file.dqd
```

Convert corpus tempate to DDL:

```bash
python -m lcpvian ddl file.json --tabwidth 4
```

List corpora and their configs:

```bash
python -m lcpvian corpora
```

Run query on corpus with id `1` (i.e. `sparcling`):

```bash
python -m lcpvian query 1 query.dqd
```

You can pass the query as a string, or as a filepath. If the filepath ends with `.json`, a JSON query is expected. Otherwise, DQD format is expected.

## Testing

Once you have started a worker, our modest backend tests can be run with:

```bash
python -m unittest
# or:
pip install coverage  # if you don't have it
coverage run -m unittest
# produce an html report of test coverage:
coverage html
```

## Deployment

1. Pull latest code
2. Edit `.env` as necessary
3. Build c extensions if you want (see above)
4. Start as many workers as necessary
5. Start app:

```bash
gunicorn --workers 3 --bind 127.0.0.1:9090 lcpvian.deploy:create_app --worker-class aiohttp.GunicornUVLoopWebWorker
```


# Running with Docker

You can run the LiRI Corpus Platform using Docker to simplify the setup and deployment process. The docker-compose.yml file included in the repository defines all the necessary services and configurations.

## Prerequisites
Ensure you have Docker and Docker Compose installed on your system.

## Running the application
To run the application using Docker, navigate to the root directory of the repository where the docker-compose.yml file is located and run one of these commands:

**For production:**
```bash
docker compose up --build
```

**For development:**
In development mode the folders are mounted into the containers. Changes made locally will reflect in the running application.
```bash
docker compose -f docker-compose.dev.yml up --build
```

## Accessing the application
Once the application is running, it will be available at:

- Application URL: http://localhost:8080
- Database: The PostgreSQL database will be available on port 15432. Only available with `docker-compose.dev.yml`.

## Docker Compose Services
The docker-compose.yml file defines several services:

- redis: Runs a Redis container
- db: Builds and runs a PostgreSQL container from the `./database` directory
- worker: Builds and runs a worker container from the `Dockerfile.worker` file
- backend: Builds and runs the backend container from the `Dockerfile.web` file.
- frontend_prod: Builds and runs the production frontend container from the `./frontend` directory
- frontend_dev: Builds and runs the development frontend container from the `Dockerfile.dev` file in the `./frontend` directory.

## Configuration
The configuration for each service is specified in the `docker-compose.yml` file. Make sure to update the `.env.docker` file with your specific environment variables as needed.
