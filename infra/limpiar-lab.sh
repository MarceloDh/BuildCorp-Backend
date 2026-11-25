#!/usr/bin/env bash
set -euo pipefail

stack=${1:?Indica el nombre de la pila temporal}
[[ $stack =~ ^buildcorp-eva4(-[a-z0-9]+)*$ ]] || { echo "Nombre de pila fuera del alcance de EVA4" >&2; exit 2; }
export AWS_DEFAULT_REGION="${AWS_REGION:-us-east-1}" AWS_PAGER=""
salidas=$(aws cloudformation describe-stacks --stack-name "$stack" --query 'Stacks[0].Outputs' --output json)
bucket=$(jq -r '.[]? | select(.OutputKey=="Bucket").OutputValue' <<<"$salidas")
resultado=0
if [[ -n $bucket ]]; then
  aws s3 rm "s3://$bucket/artefactos/buildcorp-eva4.tar.gz" --only-show-errors || resultado=1
  aws s3 rm "s3://$bucket/recursos/guia-inventario.txt" --only-show-errors || resultado=1
fi
snapshot="$stack-demostracion"
if snapshots=$(aws rds describe-db-snapshots --snapshot-type manual --query 'DBSnapshots[].DBSnapshotIdentifier' --output text); then
  if grep -qw "$snapshot" <<<"$snapshots"; then
    aws rds delete-db-snapshot --db-snapshot-identifier "$snapshot" --query 'DBSnapshot.Status' || resultado=1
  fi
else
  resultado=1
fi
parametro="/buildcorp/$stack/clave-demo"
if cantidad=$(aws ssm describe-parameters --parameter-filters "Key=Name,Option=Equals,Values=$parametro" --query 'length(Parameters)' --output text); then
  if [[ $cantidad == 1 ]]; then
    aws ssm delete-parameter --name "$parametro" || resultado=1
  fi
else
  resultado=1
fi
aws cloudformation delete-stack --stack-name "$stack"
aws cloudformation wait stack-delete-complete --stack-name "$stack"
printf 'Pila %s eliminada.\n' "$stack"
if (( resultado != 0 )); then
  printf 'Revisa los errores anteriores y los recursos externos a la pila.\n' >&2
  exit "$resultado"
fi
