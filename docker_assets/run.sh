#!/bin/bash
# startup script inside the container for tubearchivist

set -e

if [[ -n "$DJANGO_DEBUG" ]]; then
  LOGLEVEL="DEBUG"
else
  LOGLEVEL="INFO"
fi

# update yt-dlp if needed
if [[ "${TA_AUTO_UPDATE_YTDLP,,}" =~ ^(release|nightly)$ ]]; then
    echo "Updating yt-dlp..."
    preflag=$([[ "${TA_AUTO_UPDATE_YTDLP,,}" == "nightly" ]] && echo "--pre" || echo "")
    python -m pip install --user --upgrade $preflag "yt-dlp[default]" || {
        echo "yt-dlp update failed"
    }
    echo "Updating bgutil-ytdlp-pot-provider..."
    python -m pip install --user --upgrade bgutil-ytdlp-pot-provider || {
        echo "bgutil-ytdlp-pot-provider update failed"
    }
fi

# stop on pending manual migration
python manage.py ta_stop_on_error

# django setup
python manage.py migrate
python manage.py collectstatic --noinput -c

# ta setup
python manage.py ta_envcheck
python manage.py ta_connection
python manage.py ta_startup

# start all tasks
nginx &
celery -A task.celery worker \
    --loglevel=$LOGLEVEL \
    --concurrency 4 \
    --max-tasks-per-child 5 \
    --max-memory-per-child 150000 &

./beat_auto_spawn.sh &

python backend_start.py
