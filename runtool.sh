DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
docker image ls | grep java-pod-dumps || docker build -t java-pod-dumps .
open http://localhost:5001&
docker run -p 5001:5001 -v $HOME/.kube/config:/root/.kube/config:ro java-pod-dumps

