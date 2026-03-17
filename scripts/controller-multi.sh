#!/bin/bash

kli init --name controller --salt 0ACDEyMzQ1Njc4OWxtbZctrl --nopasscode --config-dir ${WITOPNET_SCRIPT_DIR} --config-file controller
kli incept --name controller --alias controller --file ${WITOPNET_SCRIPT_DIR}/data/controller.json

WITNESS=$(curl -s -XPOST http://localhost:5631/witnesses -d'{"aid": "ENcOes8_t2C7tck4X4j61fSm0sWkLbZrEZffq7mSn8On"}' -H "Content-Type: application/json")

OOBI=$(echo "${WITNESS}" | jq -r .oobis[0])
EID1=$(echo "${WITNESS}" | jq -r .eid)
echo "${WITNESS}"

kli oobi resolve --name controller --oobi-alias witopnet --oobi "${OOBI}"
WITNESS=$(curl -s -XPOST http://localhost:5631/witnesses -d'{"aid": "ENcOes8_t2C7tck4X4j61fSm0sWkLbZrEZffq7mSn8On"}' -H "Content-Type: application/json")

OOBI=$(echo "${WITNESS}" | jq -r .oobis[0])
EID2=$(echo "${WITNESS}" | jq -r .eid)

kli oobi resolve --name controller --oobi-alias witopnet --oobi "${OOBI}"

kli witness authenticate --name controller --alias controller --witness "${EID1}"
kli witness authenticate --name controller --alias controller --witness "${EID2}"

kli rotate --name controller --alias controller --witness-add "${EID1}" --witness-add "${EID2}" --receipt-endpoint --authenticate
kli status --name controller --alias controller
