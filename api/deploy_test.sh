# 把镜像打包，推到测试环境

version=$1
if [[ -z "$version" ]]; then
    echo "version variable is empty, set default 1"
    version=1
fi

docker save -o images.tar difyapi:v"$version" 
scp images.tar ec2-user@newtoio:~ 
ssh ec2-user@newtoio > /dev/null 2>&1 << eeooff
docker load -i images.tar
docker images | grep none | awk '{print $3}' | xargs docker rmi 
cd /data/www/dify/api
docker-compose down
docker-compose up -d
eeooff
echo done!