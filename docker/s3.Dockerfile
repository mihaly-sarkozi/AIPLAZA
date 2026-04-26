FROM bitnami/kubectl:latest

CMD kubectl -n minio port-forward svc/minio 9000:9000 9001:9001