# Task spooler

A tool to serialize background task execution.  Helps normalize resource usage, like CPU and network.


## How it works

1. You run the daemon.  It creates an SQLite database in your home folder and is ready to do the job.
2. You add background tasks with the `tsp` command, from cron scripts, event handlers and so on.  Example: `tsp ~/bin/fetch-mail`.
3. Tasks are executed one by one.  Logs are kept for a month.


## Usage

See current status (most recent tasks) with `tsp`:

![tsp output](https://storage.yandexcloud.net/umonkey-land/tsp.png)

See single task details:

![tsp show output](https://storage.yandexcloud.net/umonkey-land/tsp-show.png)


## Prior art

This is my remake of [ts](https://vicerveza.homeunix.net/~viric/soft/ts/), which is great!  But it has some problems which I didn't like and wanted fixed.

1. There was no explicit server.  It was created on demand by first client run.  Which didn't always work.  I often found hundreds of hanging `tsp` processes locked on a queue or something.  Not good.
2. Logs were saved as files in the `/tmp` folder, lots of them.  Purged too often, not very easy to access.
