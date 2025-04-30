import { randomBytes } from "crypto";


export function getAuthHeader(username, token) {
  const auth = `${username}:${token}`;
  const encodedAuth = Buffer.from(auth).toString("base64");
  return `Basic ${encodedAuth}`;
}

export function mergeLabelData(labels, existing_labels) {
  let mergedArray = [...labels, ...existing_labels];
  let uniqueArray = [...new Set(mergedArray)];
  return { labels: uniqueArray };
}

export function platformStatus(platform, data) {
  const platformData = data.find((item) => item.platform === platform);
  return platformData ? platformData.isConnect : false;
}

export function isLabelsMismatch(newLabels, correctedLabels, predictedLabels) {
  function check(arr, newLabels) {
    if (
      Array.isArray(newLabels) &&
      Array.isArray(arr) &&
      newLabels.length === arr.length
    ) {
      for (let label of newLabels) {
        if (!arr.includes(label)) {
          return true;
        }
      }
      return false;
    } else {
      return true;
    }
  }

  const val1 = check(correctedLabels, newLabels);
  const val2 = check(predictedLabels, newLabels);
  return val1 && val2;
}

export function getOutlookExpirationDateTime() {
  const currentDate = new Date();
  currentDate.setDate(currentDate.getDate() + 3);
  const updatedDateISOString = currentDate.toISOString();
  return updatedDateISOString;
}

export function findDuplicateStopWords(inputArray, existingArray) {
  const set1 = new Set(existingArray);
  const duplicates = inputArray.filter((item) => set1.has(item));
  const value = JSON.stringify(duplicates);
  return value;
}

export function findNotExistingStopWords(inputArray, existingArray) {
  const set1 = new Set(existingArray);
  const notExisting = inputArray.filter((item) => !set1.has(item));
  const value = JSON.stringify(notExisting);
  return value;
}

export function getRandomString() {
  const randomHexString = randomBytes(32).toString("hex");
  return randomHexString;
}

export function base64Decrypt(cipher, isObject) {
    if (!cipher) {
        return JSON.stringify({
            error: true,
            message: 'Cipher is missing',
        });
    }

    try {
        const decodedContent = !isObject ? atob(cipher) : JSON.parse(atob(cipher));
        const cleanedContent = decodedContent.replace(/\r/g, '');
        return JSON.stringify({
            error: false,
            content: cleanedContent
        });
    } catch (err) {
        return JSON.stringify({
            error: true,
            message: 'Base64 Decryption Failed',
        });
    }
}

export function base64Encrypt(content) {
    if (!content) {
        return {
            error: true,
            message: 'Content is missing',
        }
    }

    try {
        return JSON.stringify({
            error: false,
            cipher: btoa(typeof content === 'string' ? content : JSON.stringify(content))
        });
    } catch (err) {
        return JSON.stringify({
            error: true,
            message: 'Base64 Encryption Failed',
        });
    }
}

export function jsEscape(str) {
  return JSON.stringify(str).slice(1, -1)
}

export function isValidIntentName(name) {
  // Allows letters (any unicode letter), numbers, and underscores
  // Matches front-end validation with spaces replaced with underscores
  return /^[\p{L}\p{N}_]+$/u.test(name);
}
