# Readme - Backup Container

All original commands were found in official [backup-container](https://github.com/BCDevOps/backup-container) repo.

No passwords or secrets are stored in this file as it's publicly available.

## Commands

1. Prepare the config map for desired databases and execute the below given command,
```
	oc create configmap backup-conf --from-file=backup.conf
```

2. Build the backup container: Go to tools space of respective project space and run the below command 

```
	oc -n xxxxx-tools process -f backup-build.yaml -p NAME=foi-docreviewer-bkup OUTPUT_IMAGE_TAG=v1 | oc -n xxxxx-tools create -f -

```
3. Deploy the backup container 

```
	oc -n xxxxx-dev process -f backup-deploy.yaml -p NAME=foi-docreviewer-bkup -p IMAGE_NAMESPACE=xxxxx-tools -p SOURCE_IMAGE_NAME=foi-docreviewer-bkup -p TAG_NAME=v1 -p BACKUP_VOLUME_NAME=foi-docreviewer-bkup-pvc -p BACKUP_VOLUME_SIZE=20Gi -p VERIFICATION_VOLUME_SIZE=5Gi -p ENVIRONMENT_NAME=xxxxx-dev -p DATABASE_DEPLOYMENT_NAME=patroni-docreviewer  -p DATABASE_USER_KEY_NAME=app-db-username -p DATABASE_PASSWORD_KEY_NAME=app-db-password | oc -n xxxxx-dev create -f -

```

