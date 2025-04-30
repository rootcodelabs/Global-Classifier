import { NextRequest, NextResponse } from 'next/server';
import axios from 'axios';

export async function POST(req: NextRequest) {
  const { code } = await req.json();
  const clientId = process.env.NEXT_PUBLIC_CLIENT_ID || "'";
  const clientSecret = process.env.CLIENT_SECRET || "";
  const redirectUri = process.env.REDIRECT_URI || "";
  try {
    const tokenResponse = await axios.post(
      'https://login.microsoftonline.com/common/oauth2/v2.0/token',
      new URLSearchParams({
        client_id: clientId,
        scope: 'User.Read Mail.ReadWrite MailboxSettings.ReadWrite offline_access',
        code,
        redirect_uri: redirectUri,
        grant_type: 'authorization_code',
        client_secret: clientSecret,
      }).toString(),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    );

    return NextResponse.json(tokenResponse.data);
  } catch (error) {
    return NextResponse.json({ error: 'Error fetching tokens' }, { status: 500 });
  }
}
