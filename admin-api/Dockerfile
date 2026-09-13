FROM golang:1.27.1-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY *.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/admin-api .

FROM alpine:3.23.5
RUN apk add --no-cache ca-certificates && adduser -D -u 10001 app
USER app
COPY --from=build /out/admin-api /usr/local/bin/admin-api
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/admin-api"]
