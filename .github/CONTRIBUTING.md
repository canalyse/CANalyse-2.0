# How to contribute

I like to encourage you to contribute to the repository.
This should be as easy as possible for you but there are a few things to consider when contributing.
The following guidelines for contribution should be followed if you want to submit a pull request.

## How to prepare

* You need a [GitHub account](https://github.com/signup/free)
* Submit an [issue ticket](https://github.com/canalyse/CANalyse/issues) for your issue if there is no one yet.
	* Describe the issue and include steps to reproduce if it's a bug.
	* Ensure to mention the earliest version that you know is affected.
* If you are able and want to fix this, fork the repository on GitHub

## Make Changes

* In your forked repository, create a topic branch for your upcoming patch. (e.g. `feature--autoplay` or `bugfix--ios-crash`)
	* Usually this is based on the main branch.
	* Create a branch based on main; `git branch
	fix/main/my_contribution main` then checkout the new branch with `git
	checkout fix/main/my_contribution`.  Please avoid working directly on the `main` branch.
* Make sure you stick to the coding style that is used already.
* Make commits of logical units and describe them properly.
* Check for unnecessary whitespace with `git diff --check` before committing.

## Submit Changes

* Push your changes to a topic branch in your fork of the repository.
* Open a pull request to the original repository and choose the right original branch you want to patch.But _please do not close the issue yourself_.
* Even if you have write access to the repository, do not directly push or merge pull-requests. Let another team member review your pull request and approve.

# Additional Resources

* [General GitHub documentation](http://help.github.com/)
* [GitHub pull request documentation](https://help.github.com/articles/about-pull-requests/)
* [Read the Issue Guidelines by @necolas](https://github.com/necolas/issue-guidelines/blob/master/CONTRIBUTING.md) for more details
