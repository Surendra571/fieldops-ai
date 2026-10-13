import { request } from './client';
import { MatchCandidatesRequest, MatchCandidatesResponse } from '../types/dispatch';

export async function matchCandidates(
  data: MatchCandidatesRequest
): Promise<MatchCandidatesResponse> {
  return request<MatchCandidatesResponse>('/dispatch/match-candidates', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

