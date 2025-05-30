import os
import httpx
from mcp.server.fastmcp import FastMCP
from gitingest_mcp.ingest import GitIngester
from typing import Any, Dict, Union, List, Optional

# Initialize FastMCP server
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

	Supports both public and private repositories. For private repositories,
	set the GITHUB_TOKEN environment variable with a valid GitHub personal access token.

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

		try: # Try to fetch README.md
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

	Supports both public and private repositories. For private repositories,
	set the GITHUB_TOKEN environment variable with a valid GitHub personal access token.

	Args:
		owner: The GitHub organization or username
		repo: The repository name
		branch: Optional branch name (default: None)
	"""
	url = f"https://github.com/{owner}/{repo}"

	try:
		# Create GitIngester and fetch data asynchronously
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
	file_paths: List[str],
	branch: Optional[str] = None
) -> Union[str, Dict[str, str]]:
	"""
	Get the content of specific files from a GitHub repository

	Supports both public and private repositories. For private repositories,
	set the GITHUB_TOKEN environment variable with a valid GitHub personal access token.

	Args:
		owner: The GitHub organization or username
		repo: The repository name
		file_paths: List of paths to files within the repository
		branch: Optional branch name (default: None)
	"""
	url = f"https://github.com/{owner}/{repo}"

	try:
		# Create GitIngester and fetch data asynchronously
		ingester = GitIngester(url, branch=branch)
		await ingester.fetch_repo_data()
		
		# Get the requested file contents
		if hasattr(ingester, '_tree_data') and ingester.github_token:
			# For GitHub API fetched repos, use async method
			files_content = await ingester._get_files_content_async(file_paths)
		else:
			# For standard gitingest repos, use sync method
			files_content = ingester.get_content(file_paths)
		
		if not files_content:
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
  mcp.run(transport='stdio')

if __name__ == "__main__":
	# Initialize and run the server
	main()
