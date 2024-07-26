 
version=$1
if [[ -z "$version" ]]; then
    echo "version variable is empty, set default 1"
    version=1
else
    echo "version variable is not empty"
fi

docker buildx build --platform linux/amd64 -t difyapi:v"$version" -f Dockerfile . 


docker images | grep none | awk '{print $3}' | xargs docker rmi 