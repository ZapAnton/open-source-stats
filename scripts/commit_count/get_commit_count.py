import os
import csv
import asyncio
from datetime import datetime, timedelta

import aiohttp
import aiofiles
from dateutil import rrule


class RepoStat:

    __slots__ = ('date', 'commit_count')

    def __init__(self, date: datetime, commit_count: int):
        self.date = date

        self.commit_count = commit_count

    def into_tuple(self) -> tuple:
        return (self.date.strftime('%d.%m.%Y'), self.commit_count)


class Repo:

    __slots__ = ('name', 'commits_url', 'repo_stats')

    def __init__(self, repo: dict):
        self.name = repo['name']

        self.commits_url = repo['commits_url'][:-6]

        self.repo_stats = None


async def get_repos() -> map:
    params = {
        'access_token': os.environ['GITHUB_TOKEN']
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(
                'https://api.github.com/orgs/exercism/repos',
                params=params) as response:
            repos = await response.json()

            return map(lambda repo: Repo(repo), repos)


async def get_repo_stats(repo: Repo) -> Repo:
    repo_stats = list()

    now = datetime.now()

    start_point = now - timedelta(days=31*6)

    for day in rrule.rrule(rrule.DAILY, dtstart=start_point, until=now):
        prev_day = day - timedelta(days=1)

        params = {
            'since': prev_day.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'until': day.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'access_token': os.environ['GITHUB_TOKEN']
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(repo.commits_url, params=params)\
                    as response:
                commits = await response.json()

        repo_stat = RepoStat(day, len(commits))

        repo_stats.append(repo_stat)

    repo.repo_stats = repo_stats

    return repo


async def write_result(repo: Repo):
    result_dir_path = os.path.join(os.environ['RESULT_DIR'], repo.name)

    if not os.path.exists(result_dir_path):
        os.makedirs(result_dir_path)

    result_file_path = os.path.join(result_dir_path, 'commit_count.csv')

    fields = ['date', 'commit_count']

    async with aiofiles.open(result_file_path, 'w') as result_file:
        csv_writer = csv.writer(result_file)

        await csv_writer.writerow(fields)

        repo_stats = map(
            lambda repo_stat: repo_stat.into_tuple(),
            repo.repo_stats
        )

        for data_line in repo_stats:
            await csv_writer.writerow(data_line)


async def count_commits():
    repos = await get_repos()

    repo_stats_tasks = [get_repo_stats(repo) for repo in repos]

    for stat_future in asyncio.as_completed(repo_stats_tasks):
        repo = await stat_future

        await write_result(repo)


def main():
    loop = None

    try:
        loop = asyncio.get_event_loop()

        loop.run_until_complete(count_commits())

        print('Done!')
    except Exception as ex:
        print(ex)
    finally:
        if loop:
            loop.close()


def check_envinroment_variables() -> (dict, dict):
    required_variables = {
        'RESULT_DIR': os.environ.get('RESULT_DIR'),
        'GITHUB_TOKEN': os.environ.get('GITHUB_TOKEN'),
    }

    present_variables = dict()

    missing_variables = dict()

    for name, value in required_variables.items():
        if not value:
            missing_variables[name] = value
        else:
            present_variables[name] = value

    return present_variables, missing_variables


if __name__ == '__main__':
    present_variables, missing_variables = check_envinroment_variables()

    if missing_variables:
        print(
            (
                'Some required environment variables were not set:\n{}\n\n'
                'The script is aborted.'
            ).format('\n'.join(missing_variables.keys()))
        )
    else:
        print('The following environment variables were set:')

        for k, v in present_variables.items():
            print('{}: {}'.format(k, v))

        result_dir_path = os.environ['RESULT_DIR']

        if not os.path.exists(result_dir_path):
            os.makedirs(result_dir_path)

        main()
