const { createHmac, timingSafeEqual } = require('crypto');

function verifySignature(payload, headers) {
    console.log("verifySignature method start");

    const signature = headers['x-hub-signature']; // Ensure this is the correct header
    if (!signature) {
        console.error('Signature missing');
        return false;
    }
    console.log("Received signature: " + signature);
    console.log("payload------------: " + payload);

    const SHARED_SECRET = process.env.JIRA_WEBHOOK_SECRET; // Replace with your actual shared secret
    console.log("SHARED_SECRET------------: " + SHARED_SECRET);
    const hmac = createHmac('sha256', Buffer.from(SHARED_SECRET, 'utf8'));

    const payloadString = JSON.stringify(payload);
    hmac.update(Buffer.from(payloadString, 'utf8')); // Explicitly use UTF-8 encoding

    const computedSignature = hmac.digest('hex');
    console.log("Computed signature: " + computedSignature);

    const computedSignaturePrefixed = "sha256=" + computedSignature;
    console.log("Computed signature with prefix: " + computedSignaturePrefixed);

    const isValid = timingSafeEqual(Buffer.from(computedSignaturePrefixed, 'utf8'), Buffer.from(signature, 'utf8'));
    console.log("Signature valid: " + isValid);

    return isValid;
}

module.exports = verifySignature;
