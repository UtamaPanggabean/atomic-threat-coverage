FROM python:3.12.11-alpine3.22

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY ./ /app

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["validate"]
