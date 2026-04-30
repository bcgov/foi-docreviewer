# Publication Service OpenShift Templates

This folder contains OpenShift templates for deploying `computingservices/publication-service`.

## Templates

| File | Purpose |
| --- | --- |
| `publicationservice-build.yaml` | Creates the `reviewer-publication-service` `ImageStream` and `BuildConfig`. |
| `publicationservice-deploy.yaml` | Creates the runtime `Deployment`, internal `Service`, and external `Route` on port `9085`. |
| `publicationservice-secrets.yaml` | Creates the `publication-service-secret` secret expected by the deploy template. |

## Deployment Order

Create the resources in this order:

```bash
oc process -f publicationservice-secrets.yaml \
  -p POSTGRES_URL='...' \
  -p REDIS_ADDR='redis.<namespace>.svc.cluster.local:6379' \
  -p REDIS_PASSWORD='...' \
  -p S3_ENDPOINT='...' \
  -p S3_ACCESS_KEY_ID='...' \
  -p S3_SECRET_ACCESS_KEY='...' \
  -p S3_PUBLIC_URL='...' \
  -p SITEMAP_OPENINFO_BUCKET='...' \
  -p SITEMAP_OPENINFO_PUBLIC_BASE_URL='...' \
  -p SITEMAP_PD_BUCKET='...' \
  -p SITEMAP_PD_PUBLIC_BASE_URL='...' \
  | oc apply -f -

oc process -f publicationservice-build.yaml | oc apply -f -

oc process -f publicationservice-deploy.yaml \
  -p IMAGE_NAMESPACE='<tools-namespace>' \
  -p IMAGE_STREAM_NAME_FULL='reviewer-publication-service:dev' \
  -p LOG_LEVEL='INFO' \
  -p TAG_NAME='dev' \
  | oc apply -f -
```

Prefer a stable Redis service DNS name for `REDIS_ADDR` instead of a raw ClusterIP. Example:

```text
redis.d106d6-dev.svc.cluster.local:6379
```

Using a Service DNS name avoids stale IPs when Redis pods or services are recreated.

After the build and deploy resources exist, the GitHub Actions CD workflow patches the `BuildConfig`, starts a build, tags the resulting image for the target environment, then explicitly restarts the `Deployment` rollout.

## Branch Testing

The temporary test branch `FOIMOD-4334_publication_service` is mapped by GitHub Actions to the `dev` image tag. A push to that branch builds from:

```text
computingservices/publication-service
```

and tags:

```text
reviewer-publication-service:dev
```

Remove that branch from the CD workflow after dev testing is complete.

## Runtime Notes

The service runs `/app/service` from the Docker image entrypoint. The deploy template does not pass worker-specific command arguments because the single Go process already serves HTTP and runs the Redis consumers, scheduler, and outbox publisher together.

The container exposes HTTP port `9085` and uses:

```text
/health
```

for readiness and liveness probes.

The deploy template keeps `replicas: 1` by default. This service is both an API and a long-running Redis consumer, so the correct model is a single long-lived `Deployment`, not a `CronJob` or build-only pipeline.
