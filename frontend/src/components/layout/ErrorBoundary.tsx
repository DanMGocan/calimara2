import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled render error:", error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <Card className="w-full max-w-md">
          <CardContent className="p-8 text-center">
            <h1 className="font-display text-xl font-medium text-primary mb-2">
              A apărut o eroare
            </h1>
            <p className="text-sm text-muted mb-6">
              Ceva nu a mers bine la încărcarea paginii. Te rugăm să reîncarci.
            </p>
            <Button onClick={() => window.location.reload()}>Reîncarcă</Button>
          </CardContent>
        </Card>
      </div>
    );
  }
}
