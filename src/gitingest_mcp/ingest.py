import re
import os
import asyncio
import httpx
from gitingest import ingest
from typing import Any, Dict, List, Optional

class GitIngester:

    def __init__(self, url: str, branch: Optional[str] = None):
        """Initialize the GitIngester with a repository URL."""
        self.url: str = url
        self.branch: Optional[str] = branch
        self.github_token: Optional[str] = os.getenv("GITHUB_TOKEN")
        self.is_private_repo: bool = False

        self.owner: Optional[str] = None
        self.repo: Optional[str] = None
        self._parse_github_url(url)

        if branch:
            self.url = f"{url}/tree/{branch}"
        self.summary: Optional[Dict[str, Any]] = None
        self.tree: Optional[Any] = None
        self.content: Optional[Any] = None

    def _parse_github_url(self, url: str) -> None:
        """Parse GitHub URL to extract owner and repo."""
        match = re.match(r"https://github\.com/([^/]+)/([^/]+)/?", url)
        if match:
            self.owner = match.group(1)
            self.repo = match.group(2)

    async def _check_if_private_repo(self) -> bool:
        """Check if repository is private using GitHub API."""
        if not self.owner or not self.repo or not self.github_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"token {self.github_token}",
                    "Accept": "application/vnd.github.v3+json",
                }
                response = await client.get(
                    f"https://api.github.com/repos/{self.owner}/{self.repo}",
                    headers=headers,
                )
                if response.status_code == 200:
                    repo_data = response.json()
                    return repo_data.get("private", False)
                return False
        except Exception:
            return False

    async def fetch_repo_data(self) -> None:
        """Asynchronously fetch and process repository data."""
        self.is_private_repo = await self._check_if_private_repo()

        try:
            loop = asyncio.get_event_loop()
            summary, self.tree, self.content = await loop.run_in_executor(
                None, lambda: ingest(self.url)
            )
            self.summary = self._parse_summary(summary)
        except Exception as e:
            if self.github_token and self.owner and self.repo:
                await self._fetch_via_github_api()
            else:
                raise e

    async def _fetch_via_github_api(self) -> None:
        """Fetch repository data using GitHub API for private repositories."""
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"token {self.github_token}",
                    "Accept": "application/vnd.github.v3+json",
                }

                repo_response = await client.get(
                    f"https://api.github.com/repos/{self.owner}/{self.repo}",
                    headers=headers,
                )
                repo_data = repo_response.json()

                branch_name = self.branch or repo_data.get("default_branch", "main")
                tree_response = await client.get(
                    f"https://api.github.com/repos/{self.owner}/{self.repo}/git/trees/{branch_name}?recursive=1",
                    headers=headers,
                )
                tree_data = tree_response.json()

                file_count = len(
                    [
                        item
                        for item in tree_data.get("tree", [])
                        if item["type"] == "blob"
                    ]
                )
                summary_str = f"Repository: {self.owner}/{self.repo}\nFiles analyzed: {file_count}\nEstimated tokens: Unknown (private repo via API)"

                tree_structure = self._build_tree_structure(tree_data.get("tree", []))

                self.summary = self._parse_summary(summary_str)
                self.tree = tree_structure
                self.content = "Content available via GitHub API - use git_files to fetch specific files"
                self._tree_data = tree_data.get("tree", [])

        except Exception as e:
            raise Exception(
                f"Failed to fetch private repository via GitHub API: {str(e)}"
            )

    def _build_tree_structure(self, tree_items: List[Dict]) -> str:
        """Build a tree structure string from GitHub API tree data."""
        tree_lines = []
        for item in sorted(tree_items, key=lambda x: x["path"]):
            if item["type"] == "blob":
                path_parts = item["path"].split("/")
                if (
                    not any(part.startswith(".") for part in path_parts)
                    and "components/ui" not in item["path"]
                ):
                    tree_lines.append(item["path"])
        return "\n".join(tree_lines)

    def _parse_summary(self, summary_str: str) -> Dict[str, Any]:
        """Parse the summary string into a structured dictionary."""
        summary_dict = {}

        try:
            repo_match = re.search(r"Repository: (.+)", summary_str)
            if repo_match:
                summary_dict["repository"] = repo_match.group(1).strip()
            else:
                summary_dict["repository"] = ""

            files_match = re.search(r"Files analyzed: (\d+)", summary_str)
            if files_match:
                summary_dict["num_files"] = int(files_match.group(1))
            else:
                summary_dict["num_files"] = None

            tokens_match = re.search(r"Estimated tokens: (.+)", summary_str)
            if tokens_match:
                summary_dict["token_count"] = tokens_match.group(1).strip()
            else:
                summary_dict["token_count"] = ""

        except Exception:
            summary_dict["repository"] = ""
            summary_dict["num_files"] = None
            summary_dict["token_count"] = ""

        summary_dict["raw"] = summary_str
        return summary_dict

    def get_summary(self) -> str:
        """Returns the repository summary."""
        return self.summary["raw"]

    def get_tree(self) -> Any:
        """Returns the repository tree structure."""
        return self.tree

    def get_content(self, file_paths: Optional[List[str]] = None) -> str:
        """Returns the repository content."""
        if file_paths is None:
            return self.content
        return self._get_files_content(file_paths)

    async def _get_files_content_async(self, file_paths: List[str]) -> str:
        """Async helper function to extract specific files from repository content."""
        result = {}
        for path in file_paths:
            result[path] = None

        if hasattr(self, "_tree_data") and self.github_token:
            try:
                return await self._fetch_files_via_api(file_paths)
            except Exception as e:
                return f"Error fetching files via GitHub API: {str(e)}"

        if not self.content:
            return self._format_empty_result(result)
        content_str = str(self.content)

        return self._get_files_content_sync(file_paths, content_str)

    def _get_files_content(self, file_paths: List[str]) -> str:
        """Helper function to extract specific files from repository content (sync version for gitingest content)."""
        result = {}
        for path in file_paths:
            result[path] = None

        if not self.content:
            return self._format_empty_result(result)

        content_str = str(self.content)
        return self._get_files_content_sync(file_paths, content_str)

    def _get_files_content_sync(self, file_paths: List[str], content_str: str) -> str:
        """Synchronous file content extraction from gitingest content."""
        result = {}
        for path in file_paths:
            result[path] = None

        patterns = [
            r"={50}\nFile: ([^\n]+)\n={50}",
            r"={10,}\nFile: ([^\n]+)\n={10,}",
            r"=+\s*File:\s*([^\n]+)\s*\n=+",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content_str)
            matched = False
            for match in matches:
                matched = True
                start_pos = match.end()
                filename = match.group(1).strip()
                next_match = re.search(pattern, content_str[start_pos:])
                if next_match:
                    end_pos = start_pos + next_match.start()
                    file_content = content_str[start_pos:end_pos].strip()
                else:
                    file_content = content_str[start_pos:].strip()

                for path in file_paths:
                    # Simple and direct matching approach
                    # 1. Exact match first (most common case)
                    if path == filename:
                        result[path] = file_content
                    # 2. Check if the found file path ends with the requested path
                    elif filename.endswith("/" + path):
                        result[path] = file_content
                    # 3. Fallback to filename matching for edge cases
                    elif path.split("/")[-1] == filename.split("/")[-1]:
                        result[path] = file_content

            if matched:
                break

        concatenated = ""
        for path, content in result.items():
            if content is not None:
                if concatenated:
                    concatenated += "\n\n"
                concatenated += f"==================================================\nFile: {path}\n==================================================\n{content}"
        return concatenated

    def _format_empty_result(self, result: Dict[str, Any]) -> str:
        """Format empty result when no content is available."""
        concatenated = ""
        for path, content in result.items():
            if concatenated:
                concatenated += "\n\n"
            concatenated += f"==================================================\nFile: {path}\n==================================================\nFile not found or no content available"
        return concatenated

    async def _fetch_files_via_api(self, file_paths: List[str]) -> str:
        """Fetch specific files via GitHub API for private repositories."""
        result = {}
        for path in file_paths:
            result[path] = None

        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"token {self.github_token}",
                    "Accept": "application/vnd.github.v3+json",
                }

                for file_path in file_paths:
                    try:
                        actual_path = self._find_file_in_tree(file_path)
                        if not actual_path:
                            result[file_path] = (
                                f"[File not found in repository tree. Available files can be seen with git_tree tool]"
                            )
                            continue

                        response = await client.get(
                            f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{actual_path}",
                            headers=headers,
                            params={"ref": self.branch} if self.branch else {},
                        )

                        if response.status_code == 200:
                            file_data = response.json()
                            if file_data.get("type") == "file":
                                import base64

                                try:
                                    content = base64.b64decode(
                                        file_data["content"]
                                    ).decode("utf-8")
                                    result[file_path] = content
                                except UnicodeDecodeError:
                                    result[file_path] = (
                                        f"[Binary file - cannot display content]"
                                    )
                            else:
                                result[file_path] = (
                                    f"[Directory or unsupported file type]"
                                )
                        else:
                            result[file_path] = (
                                f"[File not found at path '{actual_path}' - HTTP {response.status_code}]"
                            )
                    except Exception as e:
                        result[file_path] = f"[Error fetching file: {str(e)}]"
                        continue

                concatenated = ""
                for path, content in result.items():
                    if content is not None:
                        if concatenated:
                            concatenated += "\n\n"
                        concatenated += f"==================================================\nFile: {path}\n==================================================\n{content}"

                return concatenated

        except Exception as e:
            raise Exception(f"Failed to fetch files via GitHub API: {str(e)}")

    def _find_file_in_tree(self, requested_path: str) -> Optional[str]:
        """Find the actual file path in the repository tree data."""
        if not hasattr(self, "_tree_data"):
            return None

        for item in self._tree_data:
            if item["type"] == "blob" and item["path"] == requested_path:
                return item["path"]

        requested_filename = requested_path.split("/")[-1]
        for item in self._tree_data:
            if item["type"] == "blob":
                filename = item["path"].split("/")[-1]
                if filename == requested_filename:
                    return item["path"]

        for item in self._tree_data:
            if item["type"] == "blob":
                filename = item["path"].split("/")[-1]
                if filename.lower() == requested_filename.lower():
                    return item["path"]

        for item in self._tree_data:
            if item["type"] == "blob" and item["path"].endswith(requested_path):
                return item["path"]

        return None
