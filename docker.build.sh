img=yt2jf_playsync
tag=0.7.5
tag_latest=true
full_img=$img:$tag
code_verison=$(git rev-parse HEAD)
echo "[core]
docker_version=$tag
code_version=$code_verison" > version.txt
docker build -t $full_img .
if [[ "$tag_latest" == "true" ]]; then
  docker tag $img:$tag $img:latest
fi