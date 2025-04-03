if git diff --quiet && git diff --cached --quiet; then
    : # No uncommitted changes, can proceed
else
    echo "You have uncommitted changes! Resolve and then try again"
    exit 3
fi
all_versions=$(git ls-remote --tags --sort='v:refname' https://github.com/serg-bloim/yt2jf_playsync.git 'v*' | cut -d/ -f3-)
latest_version=$(echo "$all_versions" | tail -n1)
echo "Latest version is: ${latest_version#v}"
echo

read -p "New version: " user_version
pattern='^[0-9]+\.[0-9]+\.[0-9]+$'
if ! [[ $user_version =~ $pattern ]]; then
    echo "Invalid input, should be like '3.4.5'"
    exit 1
fi
tag_name="v$user_version"
if git rev-parse "$tag_name" >/dev/null 2>&1; then
    echo "Tag $tag_name already exists! Version must be new."
    exit 2
fi

echo "Version is good $user_version"

sed "2s/.*/tag=$user_version/" docker.build.sh > docker.build.sh.tmp && mv docker.build.sh.tmp docker.build.sh
git add docker.build.sh
git commit -m "Release version $user_version"
git tag "$tag_name"

echo "Release is ready for a push"