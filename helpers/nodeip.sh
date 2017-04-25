#!/bin/bash
SERVICE_NAME=$1
TASK_ID="$(docker service ps -q ${SERVICE_NAME})"
CONT_ID="$(docker inspect -f "{{.Status.ContainerStatus.ContainerID}}" ${TASK_ID})"
NODE_ID="$(docker inspect -f "{{.NodeID}}" ${TASK_ID})"
NODE_IP="$(docker inspect -f {{.Status.Addr}} ${NODE_ID})"
echo -e "{\"nodeip\":\""$NODE_IP"\", \"containerid\":\""$CONT_ID"\"}"
