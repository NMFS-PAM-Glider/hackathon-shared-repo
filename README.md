# hackathon-shared-repo
A place to share hackathon code projects.

## Instructions for forking and creating a pull request
1.Fork the Repository:Performed on GitHub / GitLab.Navigate to the main repository on GitHub (or your Git host) and click the Fork button in the top right. Select your account to create a personal server-side copy.2.Clone Your Fork Locally:Terminal / Command Line.Clone your forked copy to your local machine:Bashgit clone https://github.com/YOUR-USERNAME/repository-name.git
cd repository-name
3.Add the Original Repo as Upstream:Prerequisite for keeping your fork synced.Link your local repository back to the original project so you can pull future updates:Bashgit remote add upstream https://github.com/ORIGINAL-OWNER/repository-name.git
4.Create a New Branch:Isolate your changes.Never make changes directly on main. Create a dedicated feature branch for your work:Bashgit checkout -b feature/my-new-feature
5.Make and Commit Your Changes:Local development.Edit the files as needed, stage your changes, and save a commit with a clear message:Bashgit add .
git commit -m "Add short, descriptive summary of changes"
6.Push Branch to Your Fork:Send changes to your remote copy.Push your newly created branch up to your personal fork on GitHub:Bashgit push origin feature/my-new-feature
7.Open a Pull Request:Performed on GitHub.Go to the original repository on GitHub (a banner will usually appear saying "Compare & pull request").Click Compare & pull request.Ensure the base repository points to the original project and the head repository points to your fork's branch.Fill in the title and description explaining your changes, then click Create Pull Request.
