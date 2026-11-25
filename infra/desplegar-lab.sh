#!/usr/bin/env bash
set -euo pipefail

stack=${1:-buildcorp-eva4}
region=${AWS_REGION:-us-east-1}
export AWS_DEFAULT_REGION="$region" AWS_PAGER=""
base=$(cd -- "$(dirname -- "$0")" && pwd)
archivo=${2:-"$base/buildcorp-eva4.tar.gz"}
clave_archivo=${3:-"$base/clave-demo"}
[[ -r $archivo && -r $clave_archivo ]]

aws cloudformation deploy --stack-name "$stack" --template-file "$base/aws-eva4.yml" \
  --no-fail-on-empty-changeset --tags Proyecto=BuildCorp Evaluacion=EVA4 Temporal=si
salidas=$(aws cloudformation describe-stacks --stack-name "$stack" \
  --query 'Stacks[0].Outputs' --output json)
salida() { jq -er --arg clave "$1" '.[] | select(.OutputKey == $clave).OutputValue' <<<"$salidas"; }
bucket=$(salida Bucket)
url=$(salida Url)
front=$(salida Frontend)
back=$(salida Backend)
endpoint=$(salida EndpointRds)
secreto=$(salida SecretoRds)
parametro="/buildcorp/$stack/clave-demo"
aws s3 cp "$archivo" "s3://$bucket/artefactos/buildcorp-eva4.tar.gz" --only-show-errors
aws s3 cp "$base/guia-inventario.txt" "s3://$bucket/recursos/guia-inventario.txt" \
  --content-type 'text/plain; charset=utf-8' --content-disposition 'attachment; filename=guia-inventario.txt' --only-show-errors
(
  umask 077
  parametros_demo=$(mktemp)
  trap 'rm -f -- "$parametros_demo"' EXIT
  jq -n --arg nombre "$parametro" --rawfile clave "$clave_archivo" \
    '{Name:$nombre,Type:"SecureString",Value:($clave|sub("[\r\n]+$";"")),Overwrite:true}' > "$parametros_demo"
  aws ssm put-parameter --cli-input-json "file://$parametros_demo" --query '{Version:Version}' --output json
)

instalar() {
  local modo=$1 instancia=$2 id ping comando parametros
  for intento in {1..30}; do
    ping=$(aws ssm describe-instance-information --filters "Key=InstanceIds,Values=$instancia" \
      --query 'InstanceInformationList[0].PingStatus' --output text)
    [[ $ping == Online ]] && break
    sleep 10
  done
  [[ $ping == Online ]]
  printf -v comando 'bash -c %q -- %q %q %q %q %q %q %q' \
    "$(cat "$base/instalar-ec2.sh")" "$modo" "$region" "$bucket" "$url" "$endpoint" "$secreto" "$parametro"
  parametros=$(jq -n --arg cmd "$comando" '{commands:[$cmd],executionTimeout:["900"]}')
  id=$(aws ssm send-command --instance-ids "$instancia" --document-name AWS-RunShellScript \
    --parameters "$parametros" --query 'Command.CommandId' --output text)
  printf '%s SSM %s\n' "$modo" "$id"
  for intento in {1..90}; do
    estado=$(aws ssm get-command-invocation --command-id "$id" --instance-id "$instancia" \
      --query Status --output text 2>/dev/null || true)
    case "$estado" in
      Success|Failed|Cancelled|TimedOut)
        aws ssm get-command-invocation --command-id "$id" --instance-id "$instancia" \
          --query '{Estado:Status,Salida:StandardOutputContent,Error:StandardErrorContent}'
        [[ $estado == Success ]]
        return
        ;;
    esac
    sleep 10
  done
  return 1
}

instalar frontend "$front" & pid_front=$!
instalar backend "$back" & pid_back=$!
resultado=0
wait "$pid_front" || resultado=1
wait "$pid_back" || resultado=1
[[ $resultado == 0 ]]
for intento in {1..30}; do
  if curl -fsS --max-time 8 "$url/api/v4/salud" && curl -fsS --max-time 8 -o /dev/null "$url/"; then
    printf '\nBuildCorp disponible en %s\n' "$url"
    exit 0
  fi
  sleep 5
done
exit 1
