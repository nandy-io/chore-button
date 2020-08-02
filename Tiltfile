docker_build('daemon-chore-button-nandy-io', './daemon')

k8s_yaml(kustomize('.'))

k8s_resource('daemon', port_forwards=['26734:5678'])