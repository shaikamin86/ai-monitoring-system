-- Enable Row Level Security
ALTER TABLE posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE narratives ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE influencers ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_terms ENABLE ROW LEVEL SECURITY;
ALTER TABLE hashtags ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;

-- Service role has full access (used by backend)
CREATE POLICY "Service role full access on posts" ON posts FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access on entities" ON entities FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access on narratives" ON narratives FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access on alerts" ON alerts FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access on influencers" ON influencers FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access on watch_terms" ON watch_terms FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access on hashtags" ON hashtags FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access on reports" ON reports FOR ALL USING (auth.role() = 'service_role');

-- Authenticated users can read
CREATE POLICY "Authenticated read posts" ON posts FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Authenticated read narratives" ON narratives FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Authenticated read alerts" ON alerts FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Authenticated read influencers" ON influencers FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Authenticated read watch_terms" ON watch_terms FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Authenticated read hashtags" ON hashtags FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Authenticated read entities" ON entities FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Authenticated read reports" ON reports FOR SELECT USING (auth.role() = 'authenticated');
