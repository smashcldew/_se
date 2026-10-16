FROM rust:1.85-alpine AS builder
WORKDIR /src
COPY main.rs ./
RUN rustc --edition=2021 -C opt-level=2 main.rs -o /prime-api

FROM alpine:3.21
RUN addgroup -S app && adduser -S -G app app
COPY --from=builder --chown=app:app /prime-api /usr/local/bin/prime-api
USER app
EXPOSE 7000
CMD ["/usr/local/bin/prime-api"]
