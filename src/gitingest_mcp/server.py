from mcp.server.fastmcp import FastMCP
from gitingest_mcp.ingest import GitIngester
from typing import Any, Dict, Union, List, Optional

mcp = FastMCP("gitingest-mcp")

@mcp.tool()
async def git_summary(
	owner: str, 
	repo: str, 
	branch: Optional[str] = None
) -> Union[str, Dict[str, str]]:
    """
    Get a summary of a GitHub repository that includes
            - Repo name,
            - Files in repo
            - Number of tokens in repo
            - Summary from the README.md

    Args:
            owner: The GitHub organization or username
            repo: The repository name
            branch: Optional branch name (default: None)
    """
    url = f"https://github.com/{owner}/{repo}"

    try:
        ingester = GitIngester(url, branch=branch)
        await ingester.fetch_repo_data()
        summary = ingester.get_summary()

        try:
            readme_content = ingester.get_content(["README.md"])
            if readme_content and "README.md" in readme_content:
                summary = f"{summary}\n\n{readme_content}"
        except Exception:
            pass

        return summary

    except Exception as e:
        return {
            "error": f"Failed to get repository summary: {str(e)}. Try https://gitingest.com/{url} instead"
        }

@mcp.tool()
async def git_tree(
	owner: str, 
	repo: str, 
	branch: Optional[str] = None
) -> Union[str, Dict[str, str]]:
    """
    Get the tree structure of a GitHub repository

    Args:
            owner: The GitHub organization or username
            repo: The repository name
            branch: Optional branch name (default: None)
    """
    url = f"https://github.com/{owner}/{repo}"

    try:
        ingester = GitIngester(url, branch=branch)
        await ingester.fetch_repo_data()
        return ingester.get_tree()
    except Exception as e:
        return {
            "error": f"Failed to get repository tree: {str(e)}. Try https://gitingest.com/{url} instead"
        }


@mcp.tool()
async def git_files(
    owner: str,
    repo: str,
    file_paths: str,
    branch: Optional[str] = None,
) -> Union[str, Dict[str, str]]:
    """
    Get the content of specific files from a GitHub repository

    Args:
            owner: The GitHub organization or username
            repo: The repository name
            file_paths: Comma-separated list of file paths (e.g., "README.md,src/main.py" or "backend/README.md")
            branch: Optional branch name (default: None)
    """
    url = f"https://github.com/{owner}/{repo}"

    # Parse comma-separated file paths into a list
    if not file_paths or not file_paths.strip():
        return {
            "error": "No file paths provided. Please specify at least one file path (e.g., 'backend/README.md' or 'README.md,src/main.py')."
        }

    # Split by comma and clean up whitespace
    file_paths_list = [path.strip() for path in file_paths.split(",") if path.strip()]

    if not file_paths_list:
        return {
            "error": "No valid file paths found. Please specify at least one file path (e.g., 'backend/README.md' or 'README.md,src/main.py')."
        }

    try:
        ingester = GitIngester(url, branch=branch)
        await ingester.fetch_repo_data()

        if hasattr(ingester, "_tree_data") and ingester.github_token:
            files_content = await ingester._get_files_content_async(file_paths_list)
        else:
            files_content = ingester.get_content(file_paths_list)

        # Check if any actual file content was found (not just error messages)
        if (
            not files_content
            or "File not found" in files_content
            or "[File not found" in files_content
        ):
            return {
                "error": f"None of the requested files were found in the repository"
            }
        return files_content

    except Exception as e:
        return {
            "error": f"Failed to get file content: {str(e)}. Try https://gitingest.com/{url} instead"
        }


def main():
    """Entry point for the gitingest-mcp command."""
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
