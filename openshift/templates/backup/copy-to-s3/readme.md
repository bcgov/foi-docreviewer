# Readme

This file is responsible for uploading files from `backup-container` to Object Storage.

# Setup

```bash
# Create virtual environment for local dev
python -m venv backup-copy

# Local dev setup 
# Load up virtual environment, use this when re-activating terminal
source backup-copy/bin/activate
```


## Pre-requisite for OpenShift: Backup-container pvc

This script assumes the BCGov backup-container is already running. https://github.com/BCDevOps/backup-container

This requires one change to the PVC, which can be done manually via the OpenShift web GUI, and should only take 1 min.

The backup-container pvc, normally called "foi-bkup-pvc" is by default a Read-Write-One PVC.  This won't work for us, we need ReadWriteMany.

So:

1. Create a new PVC called "foi-bkup-shared-pvc". Set type to "netapp-file-backup" (Storage > Peristent Volume Claims > Create)
2. Change backup-container to use new PVC.  Open up DeploymentConfig/backup-container yaml (eg foi-bkup), and modify instances of "foi-bkup-pvc" to "foi-bkup-shared-pvc"
3. Verification: Log onto new pod, and do `ls /backups/`.  It should be an empty folder as it's a new pvc.
4. Run `./backup.sh -1` to manually trigger a backup, then do `ls /backups/` to verify it's there.


The copy-to-s3 CronJob's PVC reference is configured per environment in the [Reviewer GitOps chart](https://github.com/bcgov-c/tenant-gitops-d106d6/tree/main/foi-doc-reviewer). Verify the referenced claim against the backup workload before changing it.

## Build the utility image

The source in this directory and `build-job.yaml` remain the utility image's build inputs. The application service catalog does not replace this build. The existing build procedure is:

```bash
# in tools
oc project ****-tools
oc process -f build-job.yaml -o yaml | oc apply -f -
oc start-build backup-to-s3-build

```

## Scheduled deployment

Argo CD manages `backup-to-s3` through the Reviewer GitOps chart in dev, test and prod. Update its image, schedule, storage and Secret references in that chart's environment values. The legacy deployment template has been retired. Preserve the backup workload and its prerequisite provisioning separately from this scheduled S3 copy.

## Trigger the cronjob manually

Want to just trigger the cronjob manually? This can be useful while developing (i.e. you don't want to wait until schedule to verify it works), or if you want to just trigger a backup.

```bash
oc create job --from=cronjob/<cronjob-name> <job-name> -n <namespace-name>
oc create job --from=cronjob/backup-to-s3 s3-job-manual-1
# Note: You will need to manually increment the job number when creating a job.
```
