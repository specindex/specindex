import corpus from "@/data/georgia-commercial-projects.json";
import type { Project, ProjectCorpus } from "./types";

const data = corpus as ProjectCorpus;

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
