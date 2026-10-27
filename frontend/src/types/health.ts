export interface HealthResponse {
  status: "ok";
  app: string;
  environment: string;
}

export interface DatabaseHealthResponse {
  status: "ok" | "unavailable";
  database: "reachable" | "unreachable";
}
