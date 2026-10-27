import { useCallback, useEffect, useState } from "react";

import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import Spinner from "../components/ui/Spinner";
import StatusPill from "../components/ui/StatusPill";
import { getErrorMessage } from "../services/api";
import { fetchDatabaseHealth, fetchHealth } from "../services/healthService";
import type { DatabaseHealthResponse, HealthResponse } from "../types/health";

interface StatusState {
  loading: boolean;
  error: string | null;
  api: HealthResponse | null;
  db: DatabaseHealthResponse | null;
}

export default function SystemStatusPage() {
  const [state, setState] = useState<StatusState>({ loading: true, error: null, api: null, db: null });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const [api, db] = await Promise.all([fetchHealth(), fetchDatabaseHealth()]);
      setState({ loading: false, error: null, api, db });
    } catch (error) {
      setState({ loading: false, error: getErrorMessage(error), api: null, db: null });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">System status</h1>
          <p className="mt-1 text-sm text-slate-500">Live checks against the backend API and database.</p>
        </div>
        <Button variant="secondary" onClick={() => void load()} disabled={state.loading}>
          Refresh
        </Button>
      </div>

      {state.loading && <Spinner label="Checking services" />}

      {!state.loading && state.error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {state.error}
        </div>
      )}

      {!state.loading && !state.error && state.api && state.db && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Card title="Backend API" description={`${state.api.app} · ${state.api.environment}`}>
            <StatusPill tone="success">Online</StatusPill>
          </Card>
          <Card title="Database" description="PostgreSQL connection">
            {state.db.database === "reachable" ? (
              <StatusPill tone="success">Reachable</StatusPill>
            ) : (
              <StatusPill tone="danger">Unreachable</StatusPill>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
