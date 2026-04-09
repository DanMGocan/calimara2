import { Helmet } from "react-helmet-async";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function RegisterPage() {
  return (
    <>
      <Helmet>
        <title>Inregistrare | Calimara</title>
      </Helmet>
      <div className="flex min-h-[60vh] items-center justify-center px-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="font-display text-3xl">Bun venit pe Calimara</CardTitle>
            <p className="text-sm text-muted mt-2">Conecteaza-te cu contul Google pentru a incepe</p>
          </CardHeader>
          <CardContent className="flex justify-center pb-8">
            <Button size="lg" asChild>
              <a href="/auth/google" className="no-underline">
                Continua cu Google
              </a>
            </Button>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
