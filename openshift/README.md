# OpenShift configuration ownership

Reviewer runtime configuration is maintained in the [Reviewer GitOps chart](https://github.com/bcgov-c/tenant-gitops-d106d6/tree/main/foi-doc-reviewer), with environment values for dev, test and prod. Argo CD manages the application Deployments, Services, Routes and the ETL, Solr-cleanup and S3-backup CronJobs.

The [service catalog](../.github/configuration/service-catalog.yaml) and [image build workflow](../.github/workflows/ci-build-images.yml) define application image builds. The [deployment workflow](../.github/workflows/cd-auto-deploy.yml) updates GitOps values after merges; [production promotion](../.github/workflows/prod-release.yml) uses the release workflow. Change runtime configuration in GitOps rather than recreating retired application templates here.

## Publishing ownership

Open information publishing, unpublishing and sitemap processing belong to [foi-flow/publication-service](https://github.com/bcgov/foi-flow/tree/main/publication-service). Its runtime configuration is in the [Flow GitOps chart](https://github.com/bcgov-c/tenant-gitops-d7abee/tree/main/foi-flow). Use the publication service's documented development setup; the old reviewer OpenInfo worker and its Compose service have been retired.

Existing cluster BuildConfigs and ImageStreams were not deleted by this repository cleanup. In particular, the old `reviewer-openinfoservice-build` references source that has been retired and must no longer be run. Operators should review cluster build retirement separately. Other legacy application BuildConfigs also remain; current application CI builds images directly. The utility image builds below retain their source and definitions.

## Why files remain here

| Area | Responsibility retained |
| --- | --- |
| Secret templates and parameter files | External prerequisite provisioning and configuration references. The reviewer chart references Secrets but does not create them. Parameters for retired workloads are retained as reference material, not as instructions to redeploy the old workload. |
| `templates/web-deploy.yaml` | Mixed legacy template includes the web ConfigMaps still mounted by the GitOps Deployment. Preserve their provisioning before retiring this file; do not apply the whole template alongside Argo. |
| `templates/backup/` | Backup workload provisioning, storage, Secrets, policy, configuration and build/recovery guidance. The database-backup Deployment is separate from the GitOps S3-copy CronJob. |
| `templates/backup/copy-to-s3/` | Source and build definition for the S3-copy image. Its scheduled runtime is in Reviewer GitOps; see its README for prerequisites and build guidance. |
| `templates/solrservices/cleardocsfromsolr/` | Source, build and Secret definition for the Solr-cleanup image. Scheduled runtime is in Reviewer GitOps. |
| `templates/documentextraction/push-to-queue/` | Source, build, Secret/parameters and legacy scheduler template. A scheduler counterpart exists in Search GitOps, but live ownership could not be verified with current access. |
| `templates/activemq/` | Storage/build/provisioning definitions and a mixed legacy runtime template. Search GitOps has an ActiveMQ counterpart; preserve non-runtime responsibilities and verify ownership before further cleanup. |
| `redis/` | Legacy Redis/sentinel and transport provisioning. A chart Service is not a replacement for these workload and infrastructure responsibilities. |
| Compression reconciliation and reviewer restart CronJobs | No equivalent job was established in the audited charts. Keep until an owner confirms migration or retirement. |

The three utility source directories above remain build contexts. Do not delete them merely because their scheduled workloads moved to Argo CD.

## Follow-up verification

Search runtime configuration is maintained in the [Search GitOps chart](https://github.com/bcgov-c/tenant-gitops-fc7a67/tree/main/foi-search). An authorized deployment owner must verify its live ownership and environment schedules before retiring the remaining Search-related runtime templates. Reviewer web ConfigMaps, backup and Redis infrastructure, utility builds and retained jobs also need explicit ownership decisions before further removal.

This cleanup changes repository assets; it does not change deployed settings or delete cluster resources. Further removals require confirmation of the retained responsibilities described above.
