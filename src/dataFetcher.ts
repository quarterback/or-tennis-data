import { SchoolData, School } from './types';

const GITHUB_OWNER = 'YOUR_GITHUB_USERNAME';
const GITHUB_REPO = 'or-tennis-data';
const GITHUB_API_BASE = 'https://api.github.com/repos';
const GITHUB_FULL_REPO = `${GITHUB_OWNER}/${GITHUB_REPO}`;

export async function fetchSchoolClassifications(): Promise<Map<string, School>> {
  const csvUrl = `https://raw.githubusercontent.com/${GITHUB_FULL_REPO}/main/master_school_list.csv`;

  try {
    const response = await fetch(csvUrl);
    const text = await response.text();
    const lines = text.split('\n');
    const schoolMap = new Map<string, School>();

    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;

      const [id, name, classification, league] = line.split(',').map(s => s.trim());
      if (id && name) {
        schoolMap.set(id, { id, name, classification, league });
      }
    }

    return schoolMap;
  } catch (error) {
    console.error('Error fetching school classifications:', error);
    return new Map();
  }
}

export async function fetchRepoContents(path: string = ''): Promise<any[]> {
  const url = `${GITHUB_API_BASE}/${GITHUB_FULL_REPO}/contents/${path}`;

  try {
    const response = await fetch(url);
    return await response.json();
  } catch (error) {
    console.error('Error fetching repo contents:', error);
    return [];
  }
}

export async function fetchJsonFile(path: string): Promise<SchoolData | null> {
  const rawUrl = `https://raw.githubusercontent.com/${GITHUB_FULL_REPO}/main/${path}`;

  try {
    const response = await fetch(rawUrl);
    return await response.json();
  } catch (error) {
    console.error(`Error fetching ${path}:`, error);
    return null;
  }
}

export async function fetchAllSchoolData(year: string): Promise<SchoolData[]> {
  const yearPath = `${year}`;
  const contents = await fetchRepoContents(yearPath);

  const jsonFiles = contents.filter((item: any) =>
    item.type === 'file' && item.name.endsWith('.json')
  );

  const schoolDataPromises = jsonFiles.map((file: any) =>
    fetchJsonFile(`${yearPath}/${file.name}`)
  );

  const results = await Promise.all(schoolDataPromises);
  return results.filter((data): data is SchoolData => data !== null);
}
