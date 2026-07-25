import nationalCorpus from "@/data/national-commercial-projects.json";
import type { Project, ProjectCorpus } from "./types";

const data = nationalCorpus as ProjectCorpus;

export function getCorpus(): ProjectCorpus {
  return data;
}

export function getProjects(): Project[] {
  return data.projects;
}

export function getProjectById(id: string): Project | undefined {
  return data.projects.find((p) => p.id === id);
}

export function getProjectIds(): string[] {
  return data.projects.map((p) => p.id);
}

export function getProjectsByState(state: string): Project[] {
  const code = state.toUpperCase();
  return data.projects.filter((p) => (p.state ?? "GA").toUpperCase() === code);
}
