"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import axios from "axios";
import styles from "../page.module.css";
import CopyableTextField from "../components/CopyableTextField";

const CallbackPage = () => {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [token, setToken] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const exchangeAuthCode = async (code: string) => {
      try {
        const response = await axios.post("/api/auth/token", { code });
        setToken(response?.data?.refresh_token);
      } catch (error) {
        setError("Error exchanging auth code!");
      }
    };

    const code = searchParams.get("code");
    if (code) {
      exchangeAuthCode(code);
    }
  }, [searchParams]);

  return (
    <Suspense fallback={<div>Loading...</div>}>
      <main className={styles.main}>
        {!token && !error && (
          <div className={styles.center}>
            <div>Retrieving the token..</div>
          </div>
        )}

        {token && (
          <div className={styles.center}>
            <div>Refresh Token </div>
            <CopyableTextField value={token} />
          </div>
        )}

      </main>
    </Suspense>
  );
};

export default CallbackPage;
