import { randomBytes } from "crypto";
import fs from "fs/promises";
import path from "path";

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
    const decodedContent = !isObject ? Buffer.from(cipher, 'base64').toString('utf8') : JSON.parse(Buffer.from(cipher, 'base64').toString('utf8'));
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
      cipher: Buffer.from(typeof content === 'string' ? content : JSON.stringify(content)).toString('base64')
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

export function eq(v1, v2) {
  return v1 === v2;
}

export function getAgencyDataHash(agencyId) {
  // Generate a random hash based on agency ID
  // Create a consistent but seemingly random hash for each agencyId
  const baseHash = agencyId.padEnd(10, agencyId); // Ensure at least 10 chars
  let hash = '';
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';

  // Use the agencyId as a seed for pseudo-randomness
  for (let i = 0; i < 16; i++) {
    // Get character code from the baseHash, or use index if out of bounds
    const charCode = i < baseHash.length ? baseHash.charCodeAt(i) : i;
    // Use the character code to get an index in our chars string
    const index = (charCode * 13 + i * 7) % chars.length;
    hash += chars[index];
  }

  return hash;
}

export function getAgencyDataAvailable(agencyId) {
  // Use agencyId as a seed for deterministic but seemingly random result
  // This ensures the same agencyId always gets the same result in the same session

  // Create a hash from the agencyId
  let hashValue = 0;
  for (let i = 0; i < agencyId.length; i++) {
    hashValue = ((hashValue << 5) - hashValue) + agencyId.charCodeAt(i);
    hashValue |= 0; // Convert to 32bit integer
  }

  // Add a time component to make it change between sessions
  // Use current date (year+month only) so it changes monthly but not every request
  const date = new Date();
  const timeComponent = date.getFullYear() * 100 + date.getMonth();

  // Combine the hash and time component for pseudo-randomness
  const combinedValue = hashValue + timeComponent;

  // Return true or false based on even/odd value
  return (combinedValue % 2) === 0;
}

export function json(context) {
  return JSON.stringify(context);
}

/**
 * Helper function to check if a value is an array
 * @param {any} value - The value to check
 * @returns {boolean} - True if value is an array, false otherwise
 */
export function isArray(value) {
  return Array.isArray(value);
}

/**
 * Returns an array of agencies that are in centopsAgencies but not in gcAgencies (by agencyId).
 * @param {Array} gcAgencies - Array of existing agencies, each with an agencyId property.
 * @param {Array} centopsAgencies - Array of agencies from CentOps, each with an agencyId property.
 * @returns {Array} Array of new agency objects from centopsAgencies.
 */
export function extractNewAgencies(gcAgencies, centopsAgencies) {
  const existingIds = new Set(gcAgencies.map(a => a.agencyId));
  const newAgencies = centopsAgencies.filter(a => !existingIds.has(a.agencyId))
  // return newAgencies;
  return JSON.stringify({
    agencies: newAgencies,
  });
}

/**
 * Downloads a JSON file from S3 and returns its parsed content.
 * @param {string} datasetId
 * @param {string|number} pageNum
 * @returns {Object} Parsed JSON content of the file
 */
export function getSingleChunkData(chunkData) { 
  const mapped = chunkData?.map(item => ({
    clientId: item.agency_id,
    id: item.id,
    clientName: item.agency_name, 
    question: item.question
  }));

  return JSON.stringify(mapped);
}

export function getPaginatedChunkIds(chunks, agencyId, pageNum, pageSize = 5) {
  let agencyRecordIndex = 0; // total agency records seen so far
  let collected = 0;         // agency records collected for this page
  let resultChunks = [];
  let startIndex = 0;
  let foundPage = false;

  for (const chunk of chunks) {
    let agencies = JSON.parse(chunk.includedAgencies.value)

    const count = agencies.filter(a => String(a) === String(agencyId)).length;
    if (count === 0) continue;

    // If we haven't reached the start of this page, skip these records
    if (!foundPage && agencyRecordIndex + count < (pageNum - 1) * pageSize + 1) {
      agencyRecordIndex += count;
      continue;
    }

    // If this is the first chunk of the page, calculate startIndex
    if (!foundPage) {
      startIndex = (pageNum - 1) * pageSize - agencyRecordIndex;
      foundPage = true;
    }

    resultChunks.push(chunk.chunkId || chunk.chunkId);
    collected += count;

    if (collected >= pageSize) break;

    agencyRecordIndex += count;
  }

  return JSON.stringify(
    {
      chunks: resultChunks,
      startIndex: startIndex
    }
  );
}

/**
 * Returns when a SigV4 presigned URL expires: X-Amz-Date + X-Amz-Expires seconds.
 * Falls back to updatedAt + 1 hour when the URL has no expiry, and to now when updatedAt is missing.
 * @param {string} presignedUrl - The presigned download URL
 * @param {string} updatedAt - When CentOps last updated the row, e.g. "2026-10-05T09:00:00"
 * @returns {string} ISO timestamp of the expiry
 */
function getPresignedUrlExpiry(presignedUrl, updatedAt) {
  try {
    const params = new URL(presignedUrl).searchParams;
    const amzDate = params.get("X-Amz-Date");
    const amzExpires = Number(params.get("X-Amz-Expires"));
    const dateMatch = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/.exec(amzDate || "");
    if (dateMatch && Number.isFinite(amzExpires) && amzExpires > 0) {
      const [, year, month, day, hour, minute, second] = dateMatch;
      const signedAt = Date.UTC(year, month - 1, day, hour, minute, second);
      return new Date(signedAt + amzExpires * 1000).toISOString();
    }
  } catch (err) {
    // Not a valid URL, use the fallback below
  }

  const hasTimezone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(updatedAt || "");
  const updatedTime = Date.parse(hasTimezone ? updatedAt : `${updatedAt}Z`);
  if (Number.isFinite(updatedTime)) {
    return new Date(updatedTime + 60 * 60 * 1000).toISOString();
  }
  return new Date().toISOString();
}

/**
 * Validates the CentOps Common Knowledge Base list and maps it to GC's agency fields.
 * @param {Array} agencies - The reply of GET /centops/integration/common-knowledge-bases
 * @returns {string} JSON string: { valid, reason, error, agencies }
 */
export function mapCentopsAgencies(agencies) {
  if (!Array.isArray(agencies)) {
    return JSON.stringify({
      valid: false,
      reason: "NOT_A_LIST",
      error: "CentOps reply is not a list",
    });
  }

  const requiredFields = ["clientId", "clientName", "partOfNetwork", "presignedUrl", "presignedUrlEtag"];
  for (let i = 0; i < agencies.length; i++) {
    const agency = agencies[i] || {};
    const missingField = requiredFields.find(
      (field) => agency[field] === undefined || agency[field] === null || agency[field] === ""
    );
    if (missingField) {
      return JSON.stringify({
        valid: false,
        reason: "MISSING_FIELD",
        error: `Agency at index ${i} is missing ${missingField}`,
      });
    }
    if (typeof agency.partOfNetwork !== "boolean") {
      return JSON.stringify({
        valid: false,
        reason: "MISSING_FIELD",
        error: `Agency at index ${i} has a partOfNetwork that is not true or false`,
      });
    }
  }

  const mapped = agencies.map((agency) => ({
    agencyId: String(agency.clientId),
    agencyName: agency.clientName,
    partOfNetwork: agency.partOfNetwork,
    presignedUrl: agency.presignedUrl,
    dataHash: String(agency.presignedUrlEtag).replace(/^"+|"+$/g, ""),
    urlExpiresAt: getPresignedUrlExpiry(agency.presignedUrl, agency.updatedAt),
  }));

  return JSON.stringify({ valid: true, agencies: mapped });
}

export function filterDataByAgency(aggregatedData, startIndex, agencyId, pageSize=5) {

  const filtered = aggregatedData.filter(item => String(item.agency_id) === String(agencyId));

  const paginated = filtered.slice(startIndex, startIndex + 5);

  const result= paginated.map(item => ({
    clientId: item.agency_id,
    id: item.id,
    clientName: item.agency_name, // No mapping available, so use agency_id
    question: item.question
  }));
  return JSON.stringify(result);
  
}

/**
 * Keeps only the classification results of agencies that are still in the network.
 * The out_of_distribution item is always kept, and is returned on its own when no agency is left.
 * @param {Array} results - Triton's top-k predictions, one list per message
 * @param {Array} agencies - The rows of get-agencies-in-network: [{ agencyId }]
 * @returns {string} JSON string: { results }
 */
export function filterClassificationToNetwork(results, agencies) {
  const inNetwork = new Set(agencies.map((agency) => String(agency.agencyId)));
  const isOutOfDistribution = (item) => item.agency_name === "out_of_distribution";

  const filtered = results.map((predictions) => {
    const kept = predictions.filter(
      (item) => isOutOfDistribution(item) || inNetwork.has(String(item.agency_id))
    );
    return kept.length > 0
      ? kept
      : [{ agency_id: 0, agency_name: "out_of_distribution", confidence: 1 }];
  });

  return JSON.stringify({ results: filtered });
}
