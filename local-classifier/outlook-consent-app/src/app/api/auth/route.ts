import { NextResponse } from 'next/server';

export async function GET() {
  const clientId = process.env.NEXT_PUBLIC_CLIENT_ID;
  const redirectUri = process.env.REDIRECT_URI ||"";
  const scope = 'User.Read Mail.ReadWrite MailboxSettings.ReadWrite offline_access';
  const state = '12345'; // You may want to generate a random state value for security
  const authUrl = `https://login.microsoftonline.com/${process.env.TENANT_ID}/oauth2/v2.0/authorize?client_id=${clientId}&response_type=code&redirect_uri=${encodeURIComponent(redirectUri)}&response_mode=query&scope=${encodeURIComponent(scope)}&state=${state}`;

  return NextResponse.redirect(authUrl);
}
